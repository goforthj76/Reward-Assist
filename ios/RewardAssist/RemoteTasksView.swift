import SwiftUI

struct RemoteTasksView: View {
    @ObservedObject var sync: ComputerSync
    @State private var devices: [String] = []
    @State private var jobs: [RemoteJob] = []
    @State private var device = ""
    @State private var app = "Nothing Bundt Cakes"
    @State private var details = ""
    @State private var confirmed = false
    @State private var busy = false
    @State private var message = ""
    @State private var requestID = UUID().uuidString
    @State private var code = ""
    struct RemoteJob: Identifiable {
        let id: String
        let device: String
        let stage: String
    }
    var body: some View {
        Form {
            Section("Home computer") {
                if devices.isEmpty { Text("No computer online. Sign in and enable Phone requests in the updated desktop app.") }
                Picker("Computer", selection:$device) {
                    Text("Choose computer").tag("")
                    ForEach(devices,id: \.self) { Text("Computer " + $0.prefix(8)).tag($0) }
                }
            }
            Section("New account setup") {
                Picker("Restaurant", selection:$app) {
                    ForEach(["Nothing Bundt Cakes","The Cheesecake Factory","Taco Bell","Dutch Bros"],id: \.self) { Text($0) }
                }
                Text("Paste the same single-person details block used on the desktop. Dutch Bros needs an attached Android device. Pickup and checkout may still need the desktop.").font(.footnote)
                TextEditor(text:$details).frame(minHeight:140).textInputAutocapitalization(.never).autocorrectionDisabled()
                Toggle("I authorize this account setup and the form submission using these details",isOn:$confirmed)
                Button("Start on computer") { Task { await submit() } }.disabled(busy || device.isEmpty || details.isEmpty || !confirmed)
            }
            Section("Recent requests") {
                ForEach(jobs) { job in
                    VStack(alignment:.leading,spacing:8) {
                        Text(job.stage.replacingOccurrences(of:"_",with:" ").capitalized).font(.headline)
                        Text("Request " + job.id.prefix(8)).font(.caption).foregroundStyle(.secondary)
                        if job.stage == "waiting_code" {
                            SecureField("Verification code",text:$code).keyboardType(.numberPad)
                            Button("Send code") { Task { await sendCode(job) } }.disabled(busy || code.count < 4 || code.count > 8)
                        }
                        if job.stage == "review_required" { Text("Review the form and terms on your computer to continue.").font(.footnote) }
                        if job.stage == "starting" { Text("If interrupted, check the computer. This request will not automatically restart.").font(.footnote) }
                    }
                }
                Button("Refresh status") { Task { await refresh() } }.disabled(busy)
                if !message.isEmpty { Text(message).font(.footnote) }
            }
        }.navigationTitle("Computer tasks")
        .task {
            while !Task.isCancelled {
                await refresh()
                do { try await Task.sleep(for:.seconds(5)) } catch { break }
            }
        }
    }
    @MainActor private func refresh() async {
        guard !busy else { return }
        do {
            let result = try await sync.remoteRead()
            devices = (result["devices"] as? [[String:Any]] ?? []).compactMap { $0["id"] as? String }
            jobs = (result["jobs"] as? [[String:Any]] ?? []).compactMap {
                guard let id=$0["id"] as? String, let device=$0["device"] as? String, let stage=$0["stage"] as? String else { return nil }
                return RemoteJob(id:id,device:device,stage:stage)
            }
        } catch { message = error.localizedDescription }
    }
    @MainActor private func submit() async {
        busy = true
        do {
            try await sync.remoteSend(action:"submit",id:requestID,device:device,content:["app":app,"details":details,"confirmed":confirmed])
            requestID = UUID().uuidString
            details = ""
            confirmed = false
            message = "Request queued. Keep the desktop app open."
        } catch { message = error.localizedDescription }
        busy = false
        await refresh()
    }
    @MainActor private func sendCode(_ job: RemoteJob) async {
        busy = true
        do {
            try await sync.remoteSend(action:"code",id:job.id,device:job.device,content:["code":code])
            code = ""
            message = "Code sent. Waiting for the computer."
        } catch { message = error.localizedDescription }
        busy = false
    }
}
