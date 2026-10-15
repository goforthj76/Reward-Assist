import SwiftUI
import UserNotifications

enum RewardDates {
    static func parse(_ value: Any?) -> Date? {
        guard let text=value as? String, !text.isEmpty else { return nil }
        let formatter=ISO8601DateFormatter()
        formatter.formatOptions=[.withInternetDateTime,.withFractionalSeconds]
        return formatter.date(from:text) ?? ISO8601DateFormatter().date(from:text)
    }
}

struct RewardCountdown: View {
    let date: Date
    var body: some View {
        TimelineView(.periodic(from:.now,by:1)) { context in
            if date > context.date {
                HStack { Image(systemName:"clock"); Text("Check reward in"); Text(date,style:.timer).monospacedDigit() }
                    .font(.caption).foregroundStyle(.teal)
            } else {
                Label("2-hour wait finished — check your reward",systemImage:"bell.badge").font(.caption).foregroundStyle(.teal)
            }
        }
    }
}

extension WalletStore {
    func scheduleBundtReminders(requestPermission: Bool) async {
        let upcoming=cards.filter { ($0.rewardCheckAt ?? .distantPast) > Date() }
        guard !upcoming.isEmpty else { return }
        let center=UNUserNotificationCenter.current()
        do {
            let settings=await center.notificationSettings()
            if settings.authorizationStatus == .notDetermined && requestPermission {
                _ = try await center.requestAuthorization(options:[.alert,.sound])
            }
            let permission=await center.notificationSettings()
            guard permission.authorizationStatus == .authorized || permission.authorizationStatus == .provisional else {
                error="Countdowns are active, but notifications are off. Allow them in iPhone Settings; LiveContainer may also need Fix Local Notifications enabled."
                return
            }
            let pending=await center.pendingNotificationRequests()
            let existing=Set(pending.map(\.identifier))
            let capacity=max(0,60-pending.count)
            let unscheduled=upcoming.sorted { $0.rewardCheckAt! < $1.rewardCheckAt! }.filter { !existing.contains("bundt-\($0.id)") }
            for card in unscheduled.prefix(capacity) {
                guard let date=card.rewardCheckAt, date > Date() else { continue }
                let content=UNMutableNotificationContent()
                content.title="Time to check your reward"
                content.body="The 2-hour Nothing Bundt Cakes wait has finished. Check your official account for availability."
                content.sound = .default
                let trigger=UNTimeIntervalNotificationTrigger(timeInterval:max(1,date.timeIntervalSinceNow),repeats:false)
                try await center.add(UNNotificationRequest(identifier:"bundt-\(card.id)",content:content,trigger:trigger))
            }
            if unscheduled.count > capacity { error="Some reminders could not be scheduled because the notification queue is full. Their countdowns remain in your wallet." }
        } catch { self.error="Could not schedule reward reminders. Your countdowns and saved accounts are unchanged." }
    }
}

struct ActivityEntry: Codable, Identifiable {
    let id: String
    var program: String
    var stage: String
    var date: Date
    var email: String?
}

@MainActor final class ActivityStore: ObservableObject {
    // Only restaurant names and status metadata; never details, passwords or codes.
    @Published private(set) var entries: [ActivityEntry] = []
    init() {
        if let data=UserDefaults.standard.data(forKey:"taskActivity"), let saved=try? JSONDecoder().decode([ActivityEntry].self,from:data) { entries=saved }
    }
    func record(id:String,program:String?,stage:String,date:Date,email:String?=nil) {
        let key=id+":"+stage
        guard !entries.contains(where:{$0.id==key}) else { return }
        let name=program ?? entries.first(where:{$0.id.hasPrefix(id+":")})?.program ?? "Computer task"
        let entryEmail = email ?? entries.first(where:{$0.id.hasPrefix(id+":")})?.email
        entries.append(ActivityEntry(id:key,program:name,stage:stage,date:date,email:entryEmail))
        entries=Array(entries.sorted{$0.date > $1.date}.prefix(200))
        if let data=try? JSONEncoder().encode(entries) { UserDefaults.standard.set(data,forKey:"taskActivity") }
    }
}

struct ActivityView: View {
    @EnvironmentObject var wallet: WalletStore
    @EnvironmentObject var activity: ActivityStore
    private var events: [ActivityEntry] {
        let accounts=wallet.cards.compactMap { card -> ActivityEntry? in
            guard let date=card.createdAt else { return nil }
            return ActivityEntry(id:card.id.uuidString,program:card.name,stage:"account_created",date:date,email:card.email)
        }
        return (activity.entries+accounts).sorted{$0.date > $1.date}
    }
    var body: some View {
        List {
            Section {
                Text("Your account history and computer task progress. Open Computer tasks to refresh remote updates; this is not a background monitor.").font(.footnote).foregroundStyle(.secondary)
            }
            let waiting=wallet.cards.filter{$0.rewardCheckAt != nil}.sorted{($0.rewardCheckAt ?? .distantPast) > ($1.rewardCheckAt ?? .distantPast)}
            if !waiting.isEmpty {
                Section("Reward reminders") {
                    ForEach(waiting) { card in
                        NavigationLink { CardDetail(id:card.id) } label: {
                            VStack(alignment:.leading,spacing:8) { Text(card.name).font(.headline); RewardCountdown(date:card.rewardCheckAt!) }
                        }
                    }
                    Button("Enable reward notifications") { Task { await wallet.scheduleBundtReminders(requestPermission:true) } }
                }
            }
            Section("Recent activity") {
                if events.isEmpty { Text("No recorded activity yet. New account dates and computer task updates will appear here.").foregroundStyle(.secondary) }
                ForEach(events) { event in
                    VStack(alignment:.leading,spacing:6) {
                        HStack {
                            Text(event.program).font(.headline)
                            Spacer()
                            if let email = event.email, !email.isEmpty {
                                Text(email)
                                    .font(.caption2.bold())
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Color.teal.opacity(0.12))
                                    .foregroundStyle(.teal)
                                    .cornerRadius(6)
                            }
                        }
                        Text(event.stage.replacingOccurrences(of:"_",with:" ").capitalized)
                        Text(event.date.formatted(date:.abbreviated,time:.shortened)).font(.caption).foregroundStyle(.secondary)
                    }.padding(.vertical,4)
                }
            }
        }.navigationTitle("Activity")
    }
}
