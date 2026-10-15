import SwiftUI
import LocalAuthentication
import UserNotifications

struct PrivacyGate<Content: View>: View {
    @Environment(\.scenePhase) private var phase
    @State private var unlocked=false
    @State private var attempted=false
    @State private var busy=false
    @State private var message=""
    @State private var context: LAContext?
    @ViewBuilder let content: () -> Content
    var body: some View {
        ZStack {
            Color(uiColor:.systemGroupedBackground).ignoresSafeArea()
            if unlocked {
                content()
                if phase != .active { Color(uiColor:.systemGroupedBackground).ignoresSafeArea().overlay(Image(systemName:"lock.fill").font(.largeTitle).foregroundStyle(.teal)) }
            }
            else {
                VStack(spacing:24) {
                    Image(systemName:"wallet.pass.fill").font(.system(size:68)).foregroundStyle(.teal)
                    Text("Your rewards.\nJust for you.").font(.largeTitle.bold()).multilineTextAlignment(.center)
                    Text("Unlock with Face ID, Touch ID or your device passcode.").foregroundStyle(.secondary).multilineTextAlignment(.center)
                    Button { Task { await unlock() } } label: { Label(busy ? "Unlocking…" : "Unlock wallet",systemImage:"faceid").frame(maxWidth:.infinity).padding(8) }.buttonStyle(.borderedProminent).tint(.teal).disabled(busy)
                    if !message.isEmpty {Text(message).font(.footnote).foregroundStyle(.secondary)}
                }.padding(32)
            }
        }.task { if phase == .active && !attempted { await unlock() } }
        .onChange(of:phase) { _, value in
            if value == .active && !attempted { Task { await unlock() } }
        }
    }
    @MainActor private func unlock() async {
        guard !busy && !unlocked else { return }
        attempted=true;busy=true;defer{busy=false;context=nil}
        let auth=LAContext();context=auth
        do { unlocked=try await auth.evaluatePolicy(.deviceOwnerAuthentication,localizedReason:"Unlock your private rewards wallet");message="" }
        catch {unlocked=false;message="Unlock was not completed. Set up a device passcode and try again. LiveContainer authentication needs testing on your device."}
    }
}

struct DashboardView: View {
    @EnvironmentObject var wallet: WalletStore
    @State private var notice=""
    @State private var secretTaps = 0
    @State private var showSecretMenu = false
    private var expiring:[RewardCard] {wallet.cards.filter {card in guard let date=card.expiresAt else{return false};return date >= Calendar.current.startOfDay(for:Date()) && date <= Date().addingTimeInterval(30*86400)}.sorted{($0.expiresAt ?? .distantFuture)<($1.expiresAt ?? .distantFuture)}}
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:24) {
                VStack(alignment:.leading,spacing:12) {
                    Text("YOUR DAILY PERKS")
                        .font(.caption.bold())
                        .tracking(2)
                        .onTapGesture {
                            secretTaps += 1
                            if secretTaps >= 5 {
                                secretTaps = 0
                                showSecretMenu = true
                            }
                        }
                    Text("Make the most\nof every visit.").font(.system(size:36,weight:.bold,design:.rounded))
                    HStack {Label("\(wallet.cards.count) accounts",systemImage:"wallet.pass");Spacer();Label("\(expiring.count) expiring",systemImage:"clock")}.font(.caption.bold())
                }.foregroundStyle(.white).padding(26).frame(maxWidth:.infinity,alignment:.leading).background(LinearGradient(colors:[Color(red:0.04,green:0.10,blue:0.22),.teal],startPoint:.topLeading,endPoint:.bottomTrailing),in:RoundedRectangle(cornerRadius:30))
                VStack(alignment:.leading,spacing:14) {
                    Text("Explore rewards").font(.title2.bold())
                    Link(destination:URL(string:"https://www.chick-fil-a.com/one")!) {
                        HStack { Image("chickfila").resizable().scaledToFit().frame(width:44,height:44); Text("Chick-fil-A · Android tablet").font(.headline) }
                    }
                    Divider()
                    Link(destination:URL(string:"https://jeremiahsice.com/rewards/")!) {
                        HStack { Image("jeremiahs").resizable().scaledToFit().frame(width:44,height:44); Text("Jeremiah's Italian Ice · Android tablet").font(.headline) }
                    }
                    Divider()
                    Link(destination:URL(string:"https://my.spendgo.com/sweetfrog")!) { HStack { Image("sweetfrog").resizable().scaledToFit().frame(width:44,height:44); Text("sweetFrog · Website") } }
                    Divider()
                    Link(destination:URL(string:"https://orders.einsteinbros.com/signup")!) { HStack { Image("einstein").resizable().scaledToFit().frame(width:44,height:44); Text("Einstein Bros. Bagels · Website · With purchase") } }
                    Text("Chick-fil-A: Enter your birthday at least 2 days in advance for the birthday reward (valid 30 days). Autonomous checkout and sync run via your paired Android tablet.").font(.footnote).foregroundStyle(.secondary)
                    Text("Einstein: free Bagel & Shmear with purchase. Jeremiah’s points QR syncs automatically from the tablet.").font(.footnote).foregroundStyle(.secondary)
                    Text("Sign up through the official program, then add your account and QR screenshot in Wallet, or sync with your computer. Multi-account batches run autonomously.").font(.footnote).foregroundStyle(.secondary)
                }.padding(20).background(Color(uiColor:.secondarySystemGroupedBackground),in:RoundedRectangle(cornerRadius:20))
                Text("Pinned for checkout").font(.title2.bold())
                let pinned=wallet.cards.filter(\.favorite)
                if pinned.isEmpty {Text("Star an account in your wallet to keep its QR card one tap away.").foregroundStyle(.secondary)}
                ForEach(pinned) {card in NavigationLink {CardDetail(id:card.id)} label:{CardTile(card:card)}.buttonStyle(.plain)}
                Text("Expiring in 30 days").font(.title2.bold())
                if expiring.isEmpty {Label("Nothing on your list expires soon",systemImage:"checkmark.circle").foregroundStyle(.secondary)}
                ForEach(expiring) {card in
                    NavigationLink {CardDetail(id:card.id)} label: {
                        HStack {Text(card.name).font(.headline);Spacer();if let date=card.expiresAt {Text(date,style:.date).font(.caption)}}.padding(18).background(Color(uiColor:.secondarySystemGroupedBackground),in:RoundedRectangle(cornerRadius:18))
                    }.buttonStyle(.plain)
                }
                NavigationLink { BirthdayCalendar() } label: {Label("Birthday calendar",systemImage:"calendar").frame(maxWidth:.infinity,alignment:.leading).padding(20).background(.teal.opacity(0.1),in:RoundedRectangle(cornerRadius:20))}
                Button("Enable reward reminders",systemImage:"bell.badge") {Task {await schedule()}}.buttonStyle(.borderedProminent).tint(.teal)
                if !notice.isEmpty {Text(notice).font(.footnote).foregroundStyle(.secondary)}
                Text("Dates and used markers are your personal tracker. Restaurant eligibility and live balances are not verified.").font(.footnote).foregroundStyle(.secondary)
                NavigationLink("Notification settings & test") {HomeView()}
            }.padding(20)
        }.background(Color(uiColor:.systemGroupedBackground)).navigationTitle("Today")
        .sheet(isPresented: $showSecretMenu) {
            SecretDiagnosticView()
        }
    }
    @MainActor private func schedule() async {
        do {
            let center=UNUserNotificationCenter.current()
            guard try await center.requestAuthorization(options:[.alert,.sound,.badge]) else {notice="Allow notifications in Settings. In LiveContainer, enable Fix Local Notifications for this app.";return}
            await wallet.scheduleBundtReminders(requestPermission:false)
            let pending=await center.pendingNotificationRequests()
            center.removePendingNotificationRequests(withIdentifiers:pending.filter{$0.identifier.hasPrefix("expiry-")}.map(\.identifier))
            var count=0
            for card in expiring.prefix(40) {
                guard let expiry = card.expiresAt else { continue }
                let reminderIntervals: [(days: Int, message: String)] = [
                    (7, "7 days left: Your \(card.name) reward expires in a week! Don't forget to use it."),
                    (3, "3 days left: Your \(card.name) reward is expiring soon!"),
                    (1, "Tomorrow: Your \(card.name) reward expires tomorrow! Last chance to redeem."),
                    (0, "Expires today: Your \(card.name) reward expires today! Check your wallet for details.")
                ]
                for rem in reminderIntervals {
                    guard let fireDate = Calendar.current.date(byAdding: .day, value: -rem.days, to: expiry),
                          let scheduledTime = Calendar.current.date(bySettingHour: 9, minute: 0, second: 0, of: fireDate),
                          scheduledTime > Date() else { continue }
                    let content = UNMutableNotificationContent()
                    content.title = "Reward Expiring: \(card.name)"
                    content.body = rem.message
                    content.sound = .default
                    let trigger = UNCalendarNotificationTrigger(dateMatching: Calendar.current.dateComponents([.year,.month,.day,.hour,.minute], from: scheduledTime), repeats: false)
                    try await center.add(UNNotificationRequest(identifier: "expiry-\(card.id)-\(rem.days)d", content: content, trigger: trigger))
                    count += 1
                }
            }
            notice="Scheduled \(count) countdown reminders (7-day, 3-day, 1-day, and day-of). Keep notifications enabled."
        } catch {notice="Could not schedule all reminders. Please try again."}
    }
}

struct SecretDiagnosticView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var status = ""
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Developer Diagnostics & Alert Testing").font(.headline)
                    Text("Test notifications on this iPhone. In LiveContainer, ensure 'Fix Local Notifications' is turned ON in app settings.").font(.footnote).foregroundStyle(.secondary)
                }
                Section("Instant notification tests") {
                    Button(action: {
                        Task {
                            let center = UNUserNotificationCenter.current()
                            _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
                            let content = UNMutableNotificationContent()
                            content.title = "Reward Assist Test Notification"
                            content.body = "Notifications are active! Your enabled reward reminders will notify you here."
                            content.sound = .default
                            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
                            try? await center.add(UNNotificationRequest(identifier: "test-alert-\(UUID().uuidString)", content: content, trigger: trigger))
                            status = "Test notification sent! Check your notification banner/lock screen."
                        }
                    }) {
                        Label("Send Test Notification Now (1s)", systemImage: "bell.fill")
                    }
                    Button(action: {
                        Task {
                            let center = UNUserNotificationCenter.current()
                            _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
                            let content = UNMutableNotificationContent()
                            content.title = "TEST — Chick-fil-A notification"
                            content.body = "This is a notification test only. No order was placed."
                            content.sound = .default
                            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 2, repeats: false)
                            try? await center.add(UNNotificationRequest(identifier: "test-cfa-once", content: content, trigger: trigger))
                            status = "Chick-fil-A Ready notification scheduled for 2 seconds!"
                        }
                    }) {
                        Label("Test 'Chick-fil-A Order Ready' Alert (2s)", systemImage: "bag.fill")
                    }
                    Button(action: {
                        Task {
                            let center = UNUserNotificationCenter.current()
                            _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
                            let content = UNMutableNotificationContent()
                            content.title = "⚠️ Reward Expiring Soon"
                            content.body = "3 days left: Your Chick-fil-A birthday reward expires soon! Open your wallet to use it."
                            content.sound = .default
                            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 2, repeats: false)
                            try? await center.add(UNNotificationRequest(identifier: "test-expiry-\(UUID().uuidString)", content: content, trigger: trigger))
                            status = "Expiring alert scheduled for 2 seconds!"
                        }
                    }) {
                        Label("Test 'Reward Expiring Soon' Alert (2s)", systemImage: "clock.badge.exclamationmark")
                    }
                }
                if !status.isEmpty {
                    Section {
                        Text(status).font(.footnote.bold()).foregroundStyle(.teal)
                    }
                }
            }
            .navigationTitle("Secret Diagnostics")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }
}
struct BirthdayCalendar: View {
    @EnvironmentObject var wallet: WalletStore
    private func cards(in month: Int) -> [RewardCard] {
        wallet.cards.filter { card in
            guard let birthday = card.birthday else { return false }
            return Calendar.current.component(.month, from: birthday) == month
        }
    }
    var body: some View {
        List {
            ForEach(1...12, id: \.self) { month in
                let entries = cards(in: month)
                if !entries.isEmpty {
                    Section(Calendar.current.monthSymbols[month - 1]) {
                        ForEach(entries) { card in
                            HStack {
                                Text(card.name)
                                Spacer()
                                if let date = card.birthday {
                                    Text(date.formatted(.dateTime.month().day())).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            if wallet.cards.allSatisfy({ $0.birthday == nil }) {
                Text("Add a birthday when saving an account to see it here.").foregroundStyle(.secondary)
            }
        }.navigationTitle("Birthdays")
    }
}
