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
    private var expiring:[RewardCard] {wallet.cards.filter {card in guard let date=card.expiresAt else{return false};return date >= Calendar.current.startOfDay(for:Date()) && date <= Date().addingTimeInterval(30*86400)}.sorted{($0.expiresAt ?? .distantFuture)<($1.expiresAt ?? .distantFuture)}}
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:24) {
                VStack(alignment:.leading,spacing:12) {
                    Text("YOUR DAILY PERKS").font(.caption.bold()).tracking(2)
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
    }
    @MainActor private func schedule() async {
        do {
            let center=UNUserNotificationCenter.current()
            guard try await center.requestAuthorization(options:[.alert,.sound]) else {notice="Allow notifications in Settings. In LiveContainer, enable Fix Local Notifications for this app.";return}
            await wallet.scheduleBundtReminders(requestPermission:false)
            let pending=await center.pendingNotificationRequests()
            center.removePendingNotificationRequests(withIdentifiers:pending.filter{$0.identifier.hasPrefix("expiry-")}.map(\.identifier))
            var count=0
            for card in expiring.prefix(50) {
                guard let date=card.expiresAt, let fire=Calendar.current.date(bySettingHour:9,minute:0,second:0,of:date), fire > Date() else {continue}
                let content=UNMutableNotificationContent();content.title="Check your rewards";content.body="A saved reward expires today. Open your wallet for details.";content.sound = .default
                let trigger=UNCalendarNotificationTrigger(dateMatching:Calendar.current.dateComponents([.year,.month,.day,.hour,.minute],from:fire),repeats:false)
                try await center.add(UNNotificationRequest(identifier:"expiry-\(card.id)",content:content,trigger:trigger));count+=1
            }
            notice="Scheduled \(count) expiration reminders at 9 AM. Enable again after changing saved dates."
        } catch {notice="Could not schedule all reminders. Please try again."}
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
