import SwiftUI
import CryptoKit
import CommonCrypto
import Security
import Darwin

private enum SyncFailure: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}

@MainActor final class ComputerSync: ObservableObject {
    @Published var accountEmail = ""
    private struct SavedSession: Codable { let email: String; let token: String; let key: Data }
    private let keychainQuery: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:"com.rewardassist.session",kSecAttrAccount as String:"cloud"]
    init() {
        var query=keychainQuery
        query[kSecReturnData as String]=true
        var result: CFTypeRef?
        if SecItemCopyMatching(query as CFDictionary,&result)==errSecSuccess,
           let data=result as? Data, let saved=try? JSONDecoder().decode(SavedSession.self,from:data),
           saved.key.count==32, UserDefaults.standard.string(forKey:"walletSyncAccount")==saved.email {
            sessionToken=saved.token; sessionKey=SymmetricKey(data:saved.key)
            accountEmail=saved.email; connected=true
            status="Signed in as " + saved.email
        }
    }
    private func remember(email:String, token:String, key:SymmetricKey) throws {
        let data=try JSONEncoder().encode(SavedSession(email:email,token:token,key:key.withUnsafeBytes { Data($0) }))
        let attributes: [String:Any]=[kSecValueData as String:data,kSecAttrAccessible as String:kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        var result=SecItemUpdate(keychainQuery as CFDictionary,attributes as CFDictionary)
        if result==errSecItemNotFound { result=SecItemAdd(keychainQuery.merging(attributes){_,new in new} as CFDictionary,nil) }
        guard result==errSecSuccess else { throw SyncFailure.message("Could not securely save your sign-in.") }
        accountEmail=email
    }
    func signOut() {
        SecItemDelete(keychainQuery as CFDictionary)
        sessionToken=nil; sessionKey=nil; connected=false; accountEmail=""
        status="Signed out. Your local wallet is still saved."
    }
    @Published var connected = false
    private var sessionToken: String?
    private var sessionKey: SymmetricKey?
    @Published var busy = false
    @Published var status = "Sign in with the same Reward Assist account as your computer."
    func sync(email: String, password: String, wallet: WalletStore) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let email = connected ? accountEmail : email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !email.isEmpty else { throw SyncFailure.message("Enter your Reward Assist email and password.") }
            if let bound = UserDefaults.standard.string(forKey: "walletSyncAccount"), bound != email {
                throw SyncFailure.message("This wallet is linked to a different Reward Assist account. Sync was stopped to avoid mixing private data.")
            }
            let token: String
            let key: SymmetricKey
            if connected, let savedToken=sessionToken, let savedKey=sessionKey {
                token=savedToken; key=savedKey
            } else {
            guard !password.isEmpty else { throw SyncFailure.message("Enter your Reward Assist password.") }
            let login = try await request("/api/auth/login", body: ["email":email,"password":password])
            guard let loginToken = login["token"] as? String else { throw SyncFailure.message("Sign-in did not return a session. Try again.") }
            token=loginToken
            let salt = Array(("reward-assist:" + email).utf8)
            let passwordBytes = Array(password.utf8)
            var derived = [UInt8](repeating: 0, count: 32)
            let result = passwordBytes.withUnsafeBytes { pass in
                salt.withUnsafeBytes { saltBuffer in
                    CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2), pass.baseAddress?.assumingMemoryBound(to: Int8.self), passwordBytes.count, saltBuffer.baseAddress?.assumingMemoryBound(to: UInt8.self), salt.count, CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), 100000, &derived, 32)
                }
            }
            guard result == kCCSuccess else { throw SyncFailure.message("Could not unlock cloud data.") }
            key = SymmetricKey(data: derived)
            }
            let response = try await request("/api/vault", token: token)
            var profile: [String:Any] = ["accounts":[],"services":[],"firstName":"","birthday":""]
            let vault = response["vault"] as? [String:Any]
            if let payload = vault?["payload"] as? String {
                guard let envelope = try JSONSerialization.jsonObject(with: Data(payload.utf8)) as? [String:Any],
                      envelope["v"] as? Int == 1,
                      let ivString = envelope["iv"] as? String, let iv = Data(base64Encoded: ivString),
                      let dataString = envelope["data"] as? String, let encrypted = Data(base64Encoded: dataString), encrypted.count >= 16 else { throw SyncFailure.message("Cloud data has an unsupported format. Nothing was changed.") }
                let box = try AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: iv), ciphertext: encrypted.dropLast(16), tag: encrypted.suffix(16))
                let plain = try AES.GCM.open(box, using: key)
                guard let decoded = try JSONSerialization.jsonObject(with: plain) as? [String:Any] else { throw SyncFailure.message("Could not read cloud accounts.") }
                profile = decoded
            }
            UserDefaults.standard.set(email, forKey: "walletSyncAccount")
            var accounts = profile["accounts"] as? [[String:Any]] ?? []
            var cards = wallet.cards
            var imported = 0
            for account in accounts {
                guard let program = (account["program"] ?? account["app"]) as? String, !program.isEmpty else { continue }
                let address = account["email"] as? String ?? ""
                let created = RewardDates.parse(account["createdAt"])
                let ready = RewardDates.parse(account["rewardCheckAt"])
                if let index=cards.firstIndex(where: { $0.name == program && $0.email.lowercased() == address.lowercased() }) {
                    if cards[index].createdAt == nil { cards[index].createdAt=created }
                    if cards[index].rewardCheckAt == nil { cards[index].rewardCheckAt=ready }
                    continue
                }
                var qr: Data?
                if let text = account["qr"] as? String, text.hasPrefix("data:image/"), let comma = text.firstIndex(of: ",") { qr = Data(base64Encoded: String(text[text.index(after: comma)...])) }
                cards.append(RewardCard(name: program, email: address, memberID: account["phone"] as? String ?? "", notes: account["notes"] as? String ?? "", password: account["password"] as? String, qr: qr, createdAt:created, rewardCheckAt:ready))
                imported += 1
            }
            var uploaded = 0
            for card in wallet.cards where !accounts.contains(where: { (($0["program"] ?? $0["app"]) as? String) == card.name && ($0["email"] as? String ?? "").lowercased() == card.email.lowercased() }) {
                accounts.append(["createdAt":card.createdAt.map { ISO8601DateFormatter().string(from:$0) } ?? "","rewardCheckAt":card.rewardCheckAt.map { ISO8601DateFormatter().string(from:$0) } ?? "","program":card.name,"email":card.email,"password":card.password ?? "","notes":card.notes,"qr":card.qr.map { "data:image/png;base64," + $0.base64EncodedString() } ?? ""])
                uploaded += 1
            }
            if uploaded > 0 {
                profile["accounts"] = accounts
                let sealed = try AES.GCM.seal(JSONSerialization.data(withJSONObject: profile), using: key)
                let envelope: [String:Any] = ["v":1,"iv":sealed.nonce.withUnsafeBytes { Data($0).base64EncodedString() },"data":(sealed.ciphertext + sealed.tag).base64EncodedString()]
                let payload = String(decoding: try JSONSerialization.data(withJSONObject: envelope), as: UTF8.self)
                _ = try await request("/api/vault", token: token, body:["payload":payload,"expected_version":vault?["version"] as? Int ?? 0], method:"PUT")
            }
            guard wallet.save(cards) else { throw SyncFailure.message("Cloud connection succeeded, but the iPhone wallet could not be saved. Please retry.") }
            await wallet.scheduleBundtReminders(requestPermission:true)
            try remember(email:email,token:token,key:key)
            sessionToken=token; sessionKey=key; connected=true
            status = "Sync complete: \(imported) downloaded, \(uploaded) uploaded. Existing entries were preserved."
        } catch { status = "Sync stopped: \(error.localizedDescription)" }
    }
    func remoteRead() async throws -> [String:Any] {
        guard let sessionToken else { throw SyncFailure.message("Sign in first.") }
        return try await request("/api/remote", token: sessionToken)
    }
    func remoteDetails(_ payload: String) throws -> [String:Any] {
        guard let key=sessionKey,
              let envelope=try JSONSerialization.jsonObject(with:Data(payload.utf8)) as? [String:Any],
              envelope["v"] as? Int == 1,
              let ivText=envelope["iv"] as? String, let iv=Data(base64Encoded:ivText),
              let text=envelope["data"] as? String, let data=Data(base64Encoded:text),data.count>=16 else { return [:] }
        let box=try AES.GCM.SealedBox(nonce:AES.GCM.Nonce(data:iv),ciphertext:data.dropLast(16),tag:data.suffix(16))
        return try JSONSerialization.jsonObject(with:AES.GCM.open(box,using:key)) as? [String:Any] ?? [:]
    }
    func remoteSend(action: String, id: String, device: String, content: [String:Any]) async throws {
        guard let sessionToken, let sessionKey else { throw SyncFailure.message("Sign in first.") }
        let sealed = try AES.GCM.seal(JSONSerialization.data(withJSONObject:content), using:sessionKey)
        let envelope: [String:Any] = ["v":1,"iv":sealed.nonce.withUnsafeBytes { Data($0).base64EncodedString() },"data":(sealed.ciphertext+sealed.tag).base64EncodedString()]
        let payload = String(decoding:try JSONSerialization.data(withJSONObject:envelope),as:UTF8.self)
        _ = try await request("/api/remote/"+action,token:sessionToken,body:["id":id,"device":device,"payload":payload])
    }
    private func request(_ path: String, token: String? = nil, body: [String:Any]? = nil, method: String? = nil) async throws -> [String:Any] {
        var request = URLRequest(url: URL(string:"https://rewards-assistant-api.mrgobeast.workers.dev" + path)!)
        request.timeoutInterval = 30
        request.httpMethod = method ?? (body == nil ? "GET" : "POST")
        request.setValue("application/json", forHTTPHeaderField:"Content-Type")
        if let token { request.setValue("Bearer " + token, forHTTPHeaderField:"Authorization") }
        if let body { request.httpBody = try JSONSerialization.data(withJSONObject: body) }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw SyncFailure.message("No response from the sync service.") }
        if http.statusCode == 401 && token != nil { signOut() }
        guard (200..<300).contains(http.statusCode) else {
            let errorBody = (try? JSONSerialization.jsonObject(with:data)) as? [String:Any]
            throw SyncFailure.message(errorBody?["message"] as? String ?? "Server returned \(http.statusCode). Check your sign-in and connection.")
        }
        return try JSONSerialization.jsonObject(with:data) as? [String:Any] ?? [:]
    }
}

enum WakeOnLAN {
    private static func discoverBroadcastAddresses() -> [String] {
        var targets = [String]()
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        if getifaddrs(&ifaddr) == 0, let first = ifaddr {
            var ptr: UnsafeMutablePointer<ifaddrs>? = first
            while let current = ptr {
                let flags = Int32(current.pointee.ifa_flags)
                let isUp = (flags & IFF_UP) != 0
                let isRunning = (flags & IFF_RUNNING) != 0
                let isLoopback = (flags & IFF_LOOPBACK) != 0
                let isBroadcast = (flags & IFF_BROADCAST) != 0

                if isUp && isRunning && !isLoopback && isBroadcast {
                    if let addr = current.pointee.ifa_addr, addr.pointee.sa_family == UInt8(AF_INET) {
                        if let dst = current.pointee.ifa_dstaddr {
                            var sin = sockaddr_in()
                            memcpy(&sin, dst, MemoryLayout<sockaddr_in>.size)
                            var ipBuf = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
                            if inet_ntop(AF_INET, &sin.sin_addr, &ipBuf, socklen_t(INET_ADDRSTRLEN)) != nil {
                                let ipStr = String(cString: ipBuf)
                                if !targets.contains(ipStr) && ipStr != "0.0.0.0" {
                                    targets.append(ipStr)
                                }
                            }
                        }
                    }
                }
                ptr = current.pointee.ifa_next
            }
            freeifaddrs(first)
        }
        if !targets.contains("255.255.255.255") {
            targets.append("255.255.255.255")
        }
        let commonSubnets = [
            "192.168.7.255", // eero /22 subnet broadcast
            "192.168.4.255",
            "192.168.4.155",
            "192.168.1.255",
            "192.168.0.255",
            "192.168.2.255",
            "10.0.0.255"
        ]
        for ip in commonSubnets {
            if !targets.contains(ip) {
                targets.append(ip)
            }
        }
        return targets
    }

    @discardableResult
    static func send(mac: String, targetIP: String = "", ports: [UInt16] = [9, 7]) -> (Bool, String) {
        let clean = mac.uppercased().replacingOccurrences(of: "[^0-9A-F]", with: "", options: .regularExpression)
        guard clean.count == 12 else {
            return (false, "Enter a valid 12-digit MAC address (e.g. 34:5A:60:BA:70:7C).")
        }
        var macBytes = [UInt8]()
        var index = clean.startIndex
        while index < clean.endIndex {
            let nextIndex = clean.index(index, offsetBy: 2)
            guard let byte = UInt8(clean[index..<nextIndex], radix: 16) else {
                return (false, "Could not parse MAC address.")
            }
            macBytes.append(byte)
            index = nextIndex
        }
        var packet = [UInt8](repeating: 0xFF, count: 6)
        for _ in 0..<16 {
            packet.append(contentsOf: macBytes)
        }

        var targets = discoverBroadcastAddresses()
        let cleanIP = targetIP.trimmingCharacters(in: .whitespacesAndNewlines)
        if !cleanIP.isEmpty && !targets.contains(cleanIP) {
            targets.insert(cleanIP, at: 0)
        }
        var successCount = 0
        var lastError: String? = nil
        let IP_ONESBCAST: Int32 = 23

        for targetIp in targets {
            for port in ports {
                let sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
                if sock < 0 {
                    lastError = "Socket error (\(errno))"
                    continue
                }

                var broadcastOpt: Int32 = 1
                setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &broadcastOpt, socklen_t(MemoryLayout<Int32>.size))
                setsockopt(sock, IPPROTO_IP, IP_ONESBCAST, &broadcastOpt, socklen_t(MemoryLayout<Int32>.size))

                var addr = sockaddr_in()
                addr.sin_family = sa_family_t(AF_INET)
                addr.sin_port = port.bigEndian
                addr.sin_addr.s_addr = inet_addr(targetIp)

                let sent = packet.withUnsafeBytes { buf in
                    withUnsafePointer(to: &addr) { addrPtr in
                        addrPtr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                            sendto(sock, buf.baseAddress, buf.count, 0, sa, socklen_t(MemoryLayout<sockaddr_in>.size))
                        }
                    }
                }
                if sent == packet.count {
                    successCount += 1
                } else if lastError == nil {
                    lastError = String(cString: strerror(errno))
                }
                close(sock)
            }
        }

        if successCount > 0 {
            return (true, "Wake signal broadcast sent! Allow 5–10 seconds for your computer to wake from sleep.")
        } else {
            let detail = lastError.map { ": \($0)" } ?? "."
            return (false, "Could not broadcast wake packet on local Wi-Fi\(detail). Verify iOS Local Network permissions are allowed in iPhone Settings > Reward Assist.")
        }
    }
}

struct ComputerSyncView: View {
    @EnvironmentObject var wallet: WalletStore
    @StateObject private var sync = ComputerSync()
    @State private var email = ""
    @State private var password = ""
    @AppStorage("enableAdvancedWake") private var showAdvancedWake = false
    @AppStorage("remoteWakeMac") private var wakeMac = ""
    @AppStorage("remoteWakeIP") private var wakeIP = ""
    @State private var wakeStatus = ""
    @State private var secretTapCount = 0

    var body: some View {
        Form {
            Section {
                Label("Your wallet, connected", systemImage:"arrow.triangle.2.circlepath")
                    .font(.title2.bold())
                    .contentShape(Rectangle())
                    .onTapGesture {
                        secretTapCount += 1
                        if secretTapCount >= 5 {
                            secretTapCount = 0
                            showAdvancedWake.toggle()
                            let generator = UINotificationFeedbackGenerator()
                            generator.notificationOccurred(.success)
                        }
                    }
                Text("Download accounts uploaded by your computer and add new iPhone accounts to your encrypted cloud vault.")
            }
            Section("Reward Assist account") {
                if sync.connected { Text("Signed in as " + sync.accountEmail); Button("Sign out",role:.destructive) { sync.signOut() } }
                if !sync.connected {
                TextField("Email", text:$email).textContentType(.username).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("Password", text:$password).textContentType(.password)
                }
                Button(sync.busy ? "Syncing…" : "Sync accounts") { Task { await sync.sync(email:email,password:password,wallet:wallet); password = "" } }.disabled(sync.busy)
                Text(sync.status).font(.footnote)
            }
            if sync.connected { Section { NavigationLink("Start a computer task") { RemoteTasksView(sync: sync) } } }

            if showAdvancedWake {
                Section("Advanced: Remote computer wake (Wake-on-LAN)") {
                    Text("Wake your sleeping Windows PC over your local Wi-Fi without leaving it running 24/7.")
                    TextField("PC MAC address (from Windows app)", text:$wakeMac)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("PC Local IP (optional)", text:$wakeIP)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button(action: {
                        let (_, msg) = WakeOnLAN.send(mac: wakeMac, targetIP: wakeIP)
                        wakeStatus = msg
                    }) {
                        Label("Wake computer now", systemImage:"bolt.fill")
                    }
                    .disabled(wakeMac.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    if !wakeStatus.isEmpty {
                        Text(wakeStatus).font(.footnote).foregroundStyle(.secondary)
                    }
                    Button("Hide advanced wake options") {
                        showAdvancedWake = false
                    }
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                }
            }

            Section("What sync includes") {
                Text("New accounts, passwords, notes and QR images. Existing entries are preserved; edits, deletions and reminder dates are currently local to this phone. Use one Reward Assist account for this wallet.")
                Text("Sign in on the desktop first so it uploads its accounts. Uploaded phone accounts are available in the cloud web wallet. Enable Phone requests on your updated desktop to start a remote setup task.")
            }
        }.navigationTitle("Computer sync")
    }
}


