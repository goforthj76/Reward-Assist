import SwiftUI

struct WakeRelayView: View {
    @ObservedObject var sync: ComputerSync
    struct Relay: Identifiable { let id:String; let device:String; let online:Bool; let result:String }
    @State private var relays:[Relay]=[]
    @State private var computers:[String]=[]
    @State private var selected=""
    @State private var pairingKey=""
    @State private var message=""
    @State private var busy=false
    @State private var waitingFor=""
    @State private var deadline:Date?
    var body:some View {
        Form {
            Section {
                Label("Your tablet is the connection home",systemImage:"ipad.and.iphone").font(.headline)
                Text("Keep your Android tablet on home Wi-Fi, powered on with its screen off. The tablet sends a local wake signal; the PC can sleep between tasks.")
            }
            Section("Paired tablet") {
                if relays.isEmpty { Text("No tablet paired yet.").foregroundStyle(.secondary) }
                ForEach(relays) { relay in
                    VStack(alignment:.leading,spacing:10) {
                        Text("Computer " + relay.device.prefix(8)).font(.headline)
                        Label(relay.online ? "Tablet online" : "Tablet offline",systemImage:relay.online ? "checkmark.circle.fill" : "wifi.slash").foregroundStyle(relay.online ? Color.green : Color.secondary)
                        if !relay.result.isEmpty { Text(resultText(relay.result)).font(.footnote) }
                        Button("Wake computer") { Task { await wake(relay) } }.disabled(busy || !relay.online || !waitingFor.isEmpty)
                        Button("Remove pairing",role:.destructive) { Task { await remove(relay) } }.disabled(busy)
                    }
                }
                if !message.isEmpty { Text(message).font(.footnote).accessibilityLabel(message) }
            }
            Section("Connect a tablet") {
                Text("First keep the PC awake with phone requests enabled. Select it, create a key, and paste the key into Reward Assist Wake Relay on Android. Enter your PC's MAC address there. Pairing again replaces the previous tablet for that PC.").font(.footnote)
                Picker("Computer",selection:$selected) {
                    Text("Choose computer").tag("")
                    ForEach(computers,id:\.self) { Text("Computer " + $0.prefix(8)).tag($0) }
                }
                Button("Create tablet pairing key") { Task { await pair() } }.disabled(busy || selected.isEmpty)
                if !pairingKey.isEmpty {
                    Text("Treat this key as private. It only lets the tablet receive and acknowledge wake requests. It expires after 90 days.").font(.caption)
                    Text(pairingKey).font(.system(.caption,design:.monospaced)).textSelection(.enabled).privacySensitive()
                    Button("Hide key") { pairingKey="" }
                }
            }
            Section {
                Text("Start with PC sleep, not power-off. Wake-on-LAN must already work on your home network. A wake signal does not unlock Windows or guarantee the computer starts. After the PC appears online, return to Computer tasks to start your request.").font(.footnote)
                Text("After restarting the tablet, open Wake Relay and enable it again. Android battery restrictions can interrupt the connection; test with the tablet screen off before relying on it away from home.").font(.footnote)
            }
        }.navigationTitle("Wake from anywhere")
        .task {
            while !Task.isCancelled {
                await refresh()
                do { try await Task.sleep(for:.seconds(5)) } catch { break }
            }
        }.onDisappear { pairingKey="" }
    }
    private func resultText(_ result:String)->String {
        switch result {
        case "queued":return "Waiting for tablet…"
        case "sending":return "Tablet received the request…"
        case "sent":return "Wake signal sent. This alone does not confirm the PC is online."
        case "failed":return "Tablet could not send the wake signal. Check its Wi-Fi and configuration."
        case "expired":return "Wake request expired. No automatic retry."
        default:return ""
        }
    }
    @MainActor private func refresh() async {
        guard !busy else{return}
        do {
            let state=try await sync.wakeRequest()
            relays=(state["relays"] as? [[String:Any]] ?? []).compactMap { row in
                guard let id=row["id"] as? String,let device=row["device"] as? String else{return nil}
                return Relay(id:id,device:device,online:row["online"] as? Bool ?? false,result:row["result"] as? String ?? "")
            }
            let remote=try await sync.remoteRead()
            computers=(remote["devices"] as? [[String:Any]] ?? []).compactMap{$0["id"] as? String}
            if !waitingFor.isEmpty {
                if computers.contains(waitingFor) {message="Computer online. Return to Computer tasks to start your request.";waitingFor="";deadline=nil}
                else if let deadline,Date()>deadline {message="Computer has not connected yet. Check sleep settings, home Wi-Fi and Reward Assist. Nothing was submitted.";waitingFor="";self.deadline=nil}
            }
        }catch{message="Wake connection needs attention: " + error.localizedDescription}
    }
    @MainActor private func pair() async {
        busy=true;defer{busy=false}
        do{let data=try await sync.wakeRequest("register",content:["device":selected]);pairingKey=data["token"] as? String ?? "";message="Paste the key into the tablet, then enable its relay."}
        catch{message=error.localizedDescription}
    }
    @MainActor private func wake(_ relay:Relay) async {
        busy=true;defer{busy=false}
        do{_ = try await sync.wakeRequest("request",content:["relay":relay.id,"id":UUID().uuidString]);waitingFor=relay.device;deadline=Date().addingTimeInterval(120);message="Wake requested. Waiting for your computer to reconnect…"}
        catch{message=error.localizedDescription}
    }
    @MainActor private func remove(_ relay:Relay) async {
        busy=true;defer{busy=false}
        do{_ = try await sync.wakeRequest("revoke",content:["relay":relay.id]);relays.removeAll{$0.id==relay.id};pairingKey="";message="Pairing removed. That tablet can no longer receive wake requests."}
        catch{message=error.localizedDescription}
    }
}
