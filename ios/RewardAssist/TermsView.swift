import SwiftUI
import WebKit

struct TermsGate: View {
    @AppStorage("acceptedTermsVersion") private var accepted = ""
    @State private var agrees = false
    var body: some View {
        if accepted == "2026-10-12" { RootView() }
        else {
            VStack(alignment: .leading, spacing: 18) {
                Label("REWARD ASSIST", systemImage: "checkmark.shield.fill").font(.caption.bold()).foregroundStyle(.teal)
                Text("Before you begin").font(.largeTitle.bold())
                Text("Read the terms, use authorized accounts, and review the actions you request.").foregroundStyle(.secondary)
                BundledTerms().clipShape(RoundedRectangle(cornerRadius:16))
                Toggle("I have read and agree to the Terms of Use", isOn:$agrees)
                Button("Agree and continue") { accepted = "2026-10-12" }
                    .buttonStyle(.borderedProminent).controlSize(.large).frame(maxWidth:.infinity).disabled(!agrees)
                Text("If you do not agree, close the app. Your choice is saved on this device.").font(.caption).foregroundStyle(.secondary)
            }.padding(24)
        }
    }
}
struct BundledTerms: UIViewRepresentable {
    func makeUIView(context: Context) -> WKWebView {
        let view = WKWebView()
        if let url = Bundle.main.url(forResource:"terms",withExtension:"html") {
            view.loadFileURL(url,allowingReadAccessTo:url.deletingLastPathComponent())
        }
        return view
    }
    func updateUIView(_ view: WKWebView, context: Context) {}
}

