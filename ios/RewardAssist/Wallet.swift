import SwiftUI
import PhotosUI
import CryptoKit
import Security
import LocalAuthentication
import UserNotifications

struct RewardCard: Codable, Identifiable {
    var id = UUID()
    var name: String
    var email: String
    var memberID: String
    var notes: String
    var password: String? = nil
    var qr: Data?
    var favorite = false
    var usedAt: Date?
    var expiresAt: Date?
    var birthday: Date?
    var createdAt: Date? = nil
    var rewardCheckAt: Date? = nil
}

@MainActor final class WalletStore: ObservableObject {
    @Published private(set) var cards: [RewardCard] = []
    @Published var error: String?
    private var key: SymmetricKey?
    private let file: URL
    init() {
        file = URL.applicationSupportDirectory.appendingPathComponent("reward-wallet.enc")
        do {
            key = try Self.loadKey()
            if FileManager.default.fileExists(atPath: file.path), let key {
                let box = try AES.GCM.SealedBox(combined: Data(contentsOf: file))
                cards = try JSONDecoder().decode([RewardCard].self, from: AES.GCM.open(box, using: key))
            }
        } catch { self.error = "Could not unlock your wallet. Your saved file has not been changed."; key = nil }
    }
    private static func loadKey() throws -> SymmetricKey {
        let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword, kSecAttrService as String:"com.rewardassist.wallet", kSecAttrAccount as String:"encryption-key"]
        var read = query; read[kSecReturnData as String] = true
        var item: CFTypeRef?
        let status = SecItemCopyMatching(read as CFDictionary, &item)
        if status == errSecSuccess, let data = item as? Data { return SymmetricKey(data: data) }
        guard status == errSecItemNotFound else { throw CocoaError(.fileReadNoPermission) }
        let key = SymmetricKey(size: .bits256)
        var add = query
        add[kSecValueData as String] = key.withUnsafeBytes { Data($0) }
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        guard SecItemAdd(add as CFDictionary, nil) == errSecSuccess else { throw CocoaError(.fileWriteNoPermission) }
        return key
    }
    @discardableResult func save(_ updated: [RewardCard]) -> Bool {
        do {
            guard let key else { throw CocoaError(.fileWriteNoPermission) }
            let sealed = try AES.GCM.seal(JSONEncoder().encode(updated), using:key)
            guard let data = sealed.combined else { throw CocoaError(.fileWriteUnknown) }
            try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            try data.write(to:file, options:[.atomic, .completeFileProtection])
            let removed = Set(cards.map(\.id)).subtracting(updated.map(\.id))
            UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: removed.flatMap { ["expiry-\($0)", "bundt-\($0)"] })
            cards = updated
            return true
        } catch { self.error = "Your change could not be saved. Please try again."; return false }
    }
    func update(_ card: RewardCard) { var all = cards; if let i = all.firstIndex(where:{$0.id == card.id}) { all[i] = card; save(all) } }
}

struct NativeWalletView: View {
    @EnvironmentObject var wallet: WalletStore
    @State private var search = ""
    @State private var adding = false
    @State private var onlyFavorites = false
    private var visible: [RewardCard] {
        wallet.cards.filter { (!onlyFavorites || $0.favorite) && (search.isEmpty || $0.name.localizedCaseInsensitiveContains(search) || $0.email.localizedCaseInsensitiveContains(search)) }
            .sorted { a,b in
                if a.createdAt != b.createdAt { return (a.createdAt ?? .distantPast) > (b.createdAt ?? .distantPast) }
                return a.id.uuidString < b.id.uuidString
            }
    }
    var body: some View {
        ScrollView {
            VStack(alignment:.leading, spacing:20) {
                VStack(alignment:.leading, spacing:8) {
                    Text("LESS SEARCHING. MORE ENJOYING.").font(.caption2.weight(.heavy)).tracking(2)
                    Text("Your everyday\nreward wallet.").font(.system(size:34, weight:.bold, design:.rounded))
                    Text("\(wallet.cards.count) saved accounts · on this device").font(.subheadline)
                }.foregroundStyle(.white).frame(maxWidth:.infinity, alignment:.leading).padding(26)
                    .background(LinearGradient(colors:[Color(red:0.05,green:0.12,blue:0.24), .teal], startPoint:.topLeading,endPoint:.bottomTrailing),in:RoundedRectangle(cornerRadius:28))
                Text("Newest accounts first · unknown creation dates appear last").font(.caption).foregroundStyle(.secondary)
                Toggle("Favorites only",isOn:$onlyFavorites).tint(.teal)
                if visible.isEmpty {
                    ContentUnavailableView(wallet.cards.isEmpty ? "Your first card belongs here" : "No matching cards", systemImage:"qrcode",description:Text("Save an account and import its rewards QR image for quick access."))
                    Button("Add an account",systemImage:"plus",action:{adding=true}).buttonStyle(.borderedProminent)
                }
                ForEach(visible) { card in
                    NavigationLink { CardDetail(id:card.id) } label: { CardTile(card:card) }.buttonStyle(.plain)
                }
                Text("Saved locally with encryption. Open Computer to sync new accounts.").font(.footnote).foregroundStyle(.secondary)
            }.padding(20)
        }.background(Color(uiColor:.systemGroupedBackground)).navigationTitle("Wallet")
            .searchable(text:$search,prompt:"Search your accounts")
            .toolbar { Button("Add",systemImage:"plus"){adding=true} }
            .sheet(isPresented:$adding) { NavigationStack { AddCardView() } }
            .alert("Wallet",isPresented:Binding(get:{wallet.error != nil},set:{if !$0 {wallet.error=nil}})) { Button("OK"){wallet.error=nil} } message: { Text(wallet.error ?? "") }
    }
}
struct CardTile: View {
    let card: RewardCard
    var body: some View {
        HStack(spacing:16) {
            Text(String(card.name.prefix(2)).uppercased()).font(.title3.bold()).foregroundStyle(.teal).frame(width:54,height:54).background(.teal.opacity(0.12),in:RoundedRectangle(cornerRadius:18))
            VStack(alignment:.leading,spacing:5) {
                Text(card.name).font(.headline)
                if let created=card.createdAt { Text("Created " + created.formatted(date:.abbreviated,time:.omitted)).font(.caption2).foregroundStyle(.secondary) }
                if let date=card.rewardCheckAt { RewardCountdown(date:date) }
                Text(card.email.isEmpty ? "Membership & rewards" : card.email).font(.caption).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer()
            Image(systemName:card.favorite ? "star.fill" : "qrcode").foregroundStyle(card.favorite ? .orange : .secondary)
        }.padding(20).background(Color(uiColor:.secondarySystemGroupedBackground),in:RoundedRectangle(cornerRadius:24))
    }
}
struct AddCardView: View {
    @EnvironmentObject var wallet: WalletStore
    @Environment(\.dismiss) var dismiss
    @State private var name=""
    @State private var email=""
    @State private var memberID=""
    @State private var notes=""
    @State private var password=""
    @State private var photo: PhotosPickerItem?
    @State private var qr: Data?
    @State private var error=""
    @State private var importing=false
    @State private var hasExpiry=false
    @State private var hasBirthday=false
    @State private var expiry=Date().addingTimeInterval(86400*7)
    @State private var birthday=Date()
    @State private var createdAt=Date()
    var body: some View {
        Form {
            Section("Account") {
                TextField("Restaurant or program",text:$name)
                TextField("Login email",text:$email).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("Password (optional)",text:$password).textContentType(.password)
                TextField("Membership number (optional)",text:$memberID)
            }
            Section("Rewards QR image") {
                PhotosPicker(selection:$photo,matching:.images) { Label(qr == nil ? "Choose QR screenshot" : "Replace QR screenshot",systemImage:"photo") }
                if importing { ProgressView("Importing image…") }
                if let qr, let image=UIImage(data:qr) { Image(uiImage:image).resizable().scaledToFit().frame(maxHeight:180) }
                Text("Import the original code supplied by the restaurant. Codes may expire or change; confirm it is current before use.").font(.footnote)
            }
            Section("Dates") {
                DatePicker("Account created",selection:$createdAt,in:...Date(),displayedComponents:[.date,.hourAndMinute])
                Toggle("Reward expires",isOn:$hasExpiry)
                if hasExpiry { DatePicker("Expiration",selection:$expiry,displayedComponents:.date) }
                Toggle("Show birthday in calendar",isOn:$hasBirthday)
                if hasBirthday { DatePicker("Birthday",selection:$birthday,in:...Date(),displayedComponents:.date) }
            }
            Section("Notes") { TextField("Offer details, pickup preference…",text:$notes,axis:.vertical).lineLimit(3...6) }
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
        }.navigationTitle("New account")
            .toolbar {
                ToolbarItem(placement:.cancellationAction) { Button("Cancel"){dismiss()} }
                ToolbarItem(placement:.confirmationAction) { Button("Save") {
                    if wallet.save(wallet.cards + [RewardCard(name:name.trimmingCharacters(in:.whitespacesAndNewlines),email:email,memberID:memberID,notes:notes,password:password.isEmpty ? nil : password,qr:qr,expiresAt:hasExpiry ? expiry : nil,birthday:hasBirthday ? birthday : nil,createdAt:createdAt,rewardCheckAt:name.localizedCaseInsensitiveContains("nothing bundt") ? createdAt.addingTimeInterval(7200) : nil)]) { Task { await wallet.scheduleBundtReminders(requestPermission:true) }; dismiss() }
                    else { error=wallet.error ?? "Could not save account." }
                }.disabled(name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || importing) }
            }
            .task(id:photo) {
                guard let photo else { return }; importing=true; defer {importing=false}
                do {
                    guard let data=try await photo.loadTransferable(type:Data.self), data.count <= 8_000_000, UIImage(data:data) != nil else { error="Choose a valid image smaller than 8 MB."; return }
                    guard !Task.isCancelled else {return}; qr=data; error=""
                } catch { self.error="Could not import that image. In LiveContainer, try enabling Fix File Picker for this app." }
            }
    }
}
struct CardDetail: View {
    @EnvironmentObject var wallet: WalletStore
    @Environment(\.dismiss) var dismiss
    let id: UUID
    @State private var fullScreen=false
    @State private var deleting=false
    @State private var revealing=false
    @State private var unlockError=""
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        if let card=wallet.cards.first(where:{$0.id==id}) {
            List {
                Section { CardTile(card:card).listRowInsets(EdgeInsets()) }
                if let qr=card.qr, let image=UIImage(data:qr) {
                    Section("Show at checkout") {
                        Button {fullScreen=true} label: {Image(uiImage:image).resizable().interpolation(.none).scaledToFit().frame(maxWidth:.infinity,maxHeight:260).padding().background(.white)}
                        Text("Tap to show full screen. Confirm the code is still valid in the restaurant app.").font(.footnote).foregroundStyle(.secondary)
                    }
                }
                Section("Account details") {
                    if let date=card.createdAt { LabeledContent("Account created",value:date.formatted(date:.abbreviated,time:.shortened)) }
                    if let date=card.rewardCheckAt { RewardCountdown(date:date); Text("Allow about 2 hours after signup, then check the official reward. This timer does not confirm issuance or eligibility.").font(.footnote) }
                    if let date=card.expiresAt {LabeledContent("Expires",value:date.formatted(date:.abbreviated,time:.omitted))}
                    if let date=card.birthday {LabeledContent("Birthday",value:date.formatted(.dateTime.month().day()))}
                    if card.name.localizedCaseInsensitiveContains("chick-fil-a") {
                        VStack(alignment:.leading, spacing:4) {
                            Label("2-Day Advance Notice Required", systemImage:"clock.badge.exclamationmark.fill").font(.caption.bold()).foregroundStyle(.red)
                            Text("Chick-fil-A requires birthdays to be entered at least 2 days prior to receive the annual birthday reward (valid for 30 days).").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    if !card.email.isEmpty { LabeledContent("Email",value:card.email).textSelection(.enabled) }
                    if !card.memberID.isEmpty { LabeledContent("Membership",value:card.memberID).textSelection(.enabled) }
                    if !card.notes.isEmpty {Text(card.notes).textSelection(.enabled)}
                    if let password=card.password, !password.isEmpty {
                        if revealing { Text(password).textSelection(.enabled); Button("Hide password"){revealing=false} }
                        else { Button("Reveal password"){Task { do { let context=LAContext(); revealing = try await context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason:"Reveal your saved account password") } catch { unlockError="Could not verify device owner. Password remains hidden." } }} }
                    }
                    if !unlockError.isEmpty {Text(unlockError).font(.footnote).foregroundStyle(.red)}
                }
                Section {
                    Button(card.favorite ? "Remove from favorites" : "Add to favorites",systemImage:"star") { var changed=card; changed.favorite.toggle(); wallet.update(changed) }
                    Button("Mark reward used today",systemImage:"checkmark.circle") {var changed=card;changed.usedAt=Date();wallet.update(changed)}
                    if let date=card.usedAt { Text("Last marked used: \(date.formatted(date:.abbreviated,time:.omitted))").font(.footnote); Button("Undo used marker"){var changed=card;changed.usedAt=nil;wallet.update(changed)} }
                    Text("This is your own tracker; it does not redeem or change the restaurant’s reward.").font(.footnote).foregroundStyle(.secondary)
                    Button("Delete account",role:.destructive){deleting=true}
                }
            }.navigationTitle(card.name).navigationBarTitleDisplayMode(.inline)
                .onChange(of:scenePhase) { _, phase in if phase != .active {revealing=false} }
                .onDisappear {revealing=false}
                .confirmationDialog("Delete this saved account?",isPresented:$deleting,titleVisibility:.visible) { Button("Delete",role:.destructive){if wallet.save(wallet.cards.filter{$0.id != id}) {dismiss()}} }
                .fullScreenCover(isPresented:$fullScreen) {
                    if let data=card.qr,let image=UIImage(data:data) { VStack { HStack {Text(card.name).font(.headline);Spacer();Button("Done"){fullScreen=false}}.padding();Spacer();Image(uiImage:image).resizable().interpolation(.none).scaledToFit().padding();Spacer();Text("Saved QR · confirm current validity").font(.footnote).padding() }.background(.white).foregroundStyle(.black) }
                }
        } else { ContentUnavailableView("Account removed",systemImage:"wallet.pass") }
    }
}
