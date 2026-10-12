import SwiftUI
import CryptoKit
import CommonCrypto

private enum SyncFailure: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}

@MainActor final class ComputerSync: ObservableObject {
    @Published var busy = false
    @Published var status = "Sign in with the same Reward Assist account as your computer."
    func sync(email: String, password: String, wallet: WalletStore) async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let email = email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !email.isEmpty, !password.isEmpty else { throw SyncFailure.message("Enter your Reward Assist email and password.") }
            if let bound = UserDefaults.standard.string(forKey: "walletSyncAccount"), bound != email {
                throw SyncFailure.message("This wallet is linked to a different Reward Assist account. Sync was stopped to avoid mixing private data.")
            }
            let login = try await request("/api/auth/login", body: ["email":email,"password":password])
            guard let token = login["token"] as? String else { throw SyncFailure.message("Sign-in did not return a session. Try again.") }
            let salt = Array(("reward-assist:" + email).utf8)
            let passwordBytes = Array(password.utf8)
            var derived = [UInt8](repeating: 0, count: 32)
            let result = passwordBytes.withUnsafeBytes { pass in
                salt.withUnsafeBytes { saltBuffer in
                    CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2), pass.baseAddress?.assumingMemoryBound(to: Int8.self), passwordBytes.count, saltBuffer.baseAddress?.assumingMemoryBound(to: UInt8.self), salt.count, CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), 100000, &derived, 32)
                }
            }
            guard result == kCCSuccess else { throw SyncFailure.message("Could not unlock cloud data.") }
            let key = SymmetricKey(data: derived)
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
                if cards.contains(where: { $0.name == program && $0.email.lowercased() == address.lowercased() }) { continue }
                var qr: Data?
                if let text = account["qr"] as? String, text.hasPrefix("data:image/"), let comma = text.firstIndex(of: ",") { qr = Data(base64Encoded: String(text[text.index(after: comma)...])) }
                cards.append(RewardCard(name: program, email: address, memberID: account["phone"] as? String ?? "", notes: account["notes"] as? String ?? "", password: account["password"] as? String, qr: qr))
                imported += 1
            }
            var uploaded = 0
            for card in wallet.cards where !accounts.contains(where: { (($0["program"] ?? $0["app"]) as? String) == card.name && ($0["email"] as? String ?? "").lowercased() == card.email.lowercased() }) {
                accounts.append(["program":card.name,"email":card.email,"password":card.password ?? "","notes":card.notes,"qr":card.qr.map { "data:image/png;base64," + $0.base64EncodedString() } ?? ""])
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
            status = "Sync complete: \(imported) downloaded, \(uploaded) uploaded. Existing entries were preserved."
        } catch { status = "Sync stopped: \(error.localizedDescription)" }
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
        guard (200..<300).contains(http.statusCode) else {
            throw SyncFailure.message(http.statusCode == 409 ? "Your computer changed the vault. Retry to fetch the latest version." : "Server returned \(http.statusCode). Check your sign-in and connection.")
        }
        return try JSONSerialization.jsonObject(with:data) as? [String:Any] ?? [:]
    }
}

struct ComputerSyncView: View {
    @EnvironmentObject var wallet: WalletStore
    @StateObject private var sync = ComputerSync()
    @State private var email = ""
    @State private var password = ""
    var body: some View {
        Form {
            Section {
                Label("Your wallet, connected", systemImage:"arrow.triangle.2.circlepath").font(.title2.bold())
                Text("Download accounts uploaded by your computer and add new iPhone accounts to your encrypted cloud vault.")
            }
            Section("Reward Assist account") {
                TextField("Email", text:$email).textContentType(.username).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("Password", text:$password).textContentType(.password)
                Button(sync.busy ? "Syncing…" : "Sync accounts") { Task { await sync.sync(email:email,password:password,wallet:wallet); password = "" } }.disabled(sync.busy)
                Text(sync.status).font(.footnote)
            }
            Section("What sync includes") {
                Text("New accounts, passwords, notes and QR images. Existing entries are preserved; edits, deletions and reminder dates are currently local to this phone. Use one Reward Assist account for this wallet.")
                Text("Sign in on the desktop first so it uploads its accounts. Uploaded phone accounts are available in the cloud web wallet. Remote computer tasks are not connected yet.")
            }
        }.navigationTitle("Computer sync")
    }
}
