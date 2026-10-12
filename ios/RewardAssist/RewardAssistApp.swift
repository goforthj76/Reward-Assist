import SwiftUI
import UserNotifications

@main
struct RewardAssistApp: App {
    @StateObject private var wallet = WalletStore()
    var body: some Scene { WindowGroup { PrivacyGate { TermsGate() }.environmentObject(wallet) } }
}

struct RootView: View {
    var body: some View {
        TabView {
            NavigationStack { DashboardView() }.tabItem { Label("Home", systemImage: "house.fill") }
            NavigationStack { NativeWalletView() }.tabItem { Label("Wallet", systemImage: "wallet.pass.fill") }
            NavigationStack {
                ContentUnavailableView("No activity yet", systemImage: "clock.arrow.circlepath", description: Text("Open Computer to view recent requests and their progress."))
                    .navigationTitle("Activity")
            }.tabItem { Label("Activity", systemImage: "clock") }
            NavigationStack { ComputerSyncView() }.tabItem { Label("Computer", systemImage: "desktopcomputer") }
        }.tint(.teal)
    }
}

struct HomeView: View {
    @State private var reminderDate = Date().addingTimeInterval(3600)
    @State private var message = ""
    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    Label("REWARD ASSIST", systemImage: "sparkles").font(.caption.bold())
                    Text("Your rewards.\nReady when you are.").font(.largeTitle.bold())
                    Text("Native iPhone preview · 0.1.0").foregroundStyle(.secondary)
                }.padding(.vertical, 16)
            }
            Section("A reminder for later") {
                DatePicker("Remind me", selection: $reminderDate, in: Date()..., displayedComponents: [.date, .hourAndMinute])
                Button("Schedule reminder") { Task { await scheduleReminder() } }
                if !message.isEmpty { Text(message).font(.footnote) }
                Text("In LiveContainer, hold this app, open its settings and enable Fix Local Notifications, then allow notifications here. Remote computer alerts are not connected in this preview.").font(.footnote).foregroundStyle(.secondary)
            }
        }.navigationTitle("Today")
    }
    @MainActor private func scheduleReminder() async {
        do {
            let center = UNUserNotificationCenter.current()
            guard try await center.requestAuthorization(options: [.alert, .sound, .badge]) else {
                message = "Notifications are not allowed. Check iPhone Settings or your sideload environment."
                return
            }
            guard reminderDate > Date() else { message = "Choose a future time."; return }
            let content = UNMutableNotificationContent()
            content.title = "Reward Assist"
            content.body = "Check your saved rewards and their expiration dates."
            content.sound = .default
            let components = Calendar.current.dateComponents([.year,.month,.day,.hour,.minute], from: reminderDate)
            let request = UNNotificationRequest(identifier: "reward-check", content: content, trigger: UNCalendarNotificationTrigger(dateMatching: components, repeats: false))
            try await center.add(request)
            message = "Reminder scheduled. Scheduling again replaces this reminder."
        } catch { message = "Could not schedule reminder: \(error.localizedDescription)" }
    }
}

struct ComputerView: View {
    var body: some View {
        List {
            Section {
                Label("Not paired", systemImage: "desktopcomputer").font(.headline)
                Text("Secure pairing is not available in this preview. No commands are sent.")
            }
            Section("How it will work") {
                Label("Online: start approved tasks", systemImage: "checkmark.circle")
                Label("Offline: queue until the computer reconnects", systemImage: "tray")
                Label("Needs input: send verification to the active task", systemImage: "person.crop.circle")
            }
            Section {
                Text("Your computer must be powered on, connected, and running the companion. Browser tasks may require an unlocked desktop. Phone requests cannot make a powered-off computer execute software.")
            }
        }.navigationTitle("Computer")
    }
}


