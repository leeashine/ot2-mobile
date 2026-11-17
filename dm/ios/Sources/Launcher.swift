// Launcher: the settings screen shown before the game starts (front_ios.m dm_show_launcher). Its settings come from the app's dm/launcher.json, which build_ipa.sh writes for this game
// from dm/games/settings.tsv (dm/games/settings.py): each sets an environment variable the host reads when the game starts. A variable an env file set (Documents/env.txt, the bundle's
// dm/env.txt; main.m lists them in DM_ENV_FILE_KEYS) is shown but kept. The choices are kept in UserDefaults. DM_LAUNCHER=0 in Documents/env.txt starts the game at once, as an app
// without launcher.json does
import SwiftUI
import UIKit
import os

private struct Setting: Decodable, Identifiable {
    let env, kind, label, note, def: String
    let options: [[String]]?   // choice: [value, label]
    let min, max, step: Double?   // range
    var id: String { env }
    enum CodingKeys: String, CodingKey { case env, kind, label, note, def = "default", options, min, max, step }
}
private struct SettingsFile: Decodable { let settings: [Setting] }

private func info(_ key: String) -> Any? { Bundle.main.object(forInfoDictionaryKey: key) }
private let defaults = UserDefaults.standard

private final class LauncherModel: ObservableObject {
    let settings: [Setting]
    let fromFile: Set<String>   // set by an env file: shown, not changed
    @Published var values: [String: String] = [:]

    init(_ settings: [Setting]) {
        self.settings = settings
        fromFile = Set((ProcessInfo.processInfo.environment["DM_ENV_FILE_KEYS"] ?? "").split(separator: " ").map(String.init))
        for s in settings {
            if fromFile.contains(s.env), let v = ProcessInfo.processInfo.environment[s.env] { values[s.env] = v; continue }
            let saved = defaults.string(forKey: "launcher." + s.env)
            values[s.env] = saved.flatMap { v in s.options == nil || s.options!.contains { $0[0] == v } ? v : nil } ?? s.def   // a saved choice the game no longer offers: its default
        }
    }

    func binding(_ s: Setting) -> Binding<String> { Binding(get: { self.values[s.env] ?? s.def }, set: { self.values[s.env] = $0 }) }

    // Before the game starts: every setting not set by an env file goes into the environment (DM_LANG replaces the packed language main.m set as a default)
    func apply() {
        for s in settings {
            let v = values[s.env] ?? s.def
            if fromFile.contains(s.env) { fputs("launcher: \(s.env) kept at \(v) (env file)\n", stderr); continue }
            defaults.set(v, forKey: "launcher." + s.env)
            setenv(s.env, v, 1); fputs("launcher: \(s.env)=\(v)\n", stderr)
        }
    }
}

private struct SettingRow: View {
    let s: Setting
    @ObservedObject var m: LauncherModel
    var body: some View {
        let locked = m.fromFile.contains(s.env)
        Section {
            switch s.kind {
            case "choice":
                // This full-screen launcher has no NavigationStack. Do not let
                // automatic picker style choose a navigation-based presentation.
                if (s.options ?? []).count == 2 {
                    VStack(alignment: .leading) {
                        Text(s.label)
                        choicePicker.pickerStyle(.segmented)
                    }
                } else {
                    choicePicker.pickerStyle(.menu)
                }
            case "range":
                let lo = s.min ?? 0, hi = s.max ?? 1
                let v = Binding<Double>(get: { Double(m.values[s.env] ?? s.def) ?? hi }, set: { m.values[s.env] = String(format: "%.2f", $0) })
                HStack {
                    Text(s.label)
                    Slider(value: v, in: lo...hi, step: s.step ?? 0.05)
                    Text("\(Int((v.wrappedValue * 100).rounded())) %").monospacedDigit().foregroundStyle(.secondary).frame(width: 56, alignment: .trailing)
                }
            default:
                Toggle(s.label, isOn: Binding(get: { (m.values[s.env] ?? s.def) == "1" }, set: { m.values[s.env] = $0 ? "1" : "0" }))
            }
        } footer: {
            let note = locked ? (s.note.isEmpty ? "" : s.note + " · ") + "Set by an env file" : s.note
            if !note.isEmpty { Text(note) }
        }
        .disabled(locked)
    }

    private var choicePicker: some View {
        Picker(s.label, selection: m.binding(s)) {
            ForEach(s.options ?? [], id: \.[0]) { Text($0[1]).tag($0[0]) }
        }
        .accessibilityIdentifier(s.env)
    }
}

private struct LauncherView: View {
    @ObservedObject var m: LauncherModel
    let play: () -> Void
    @State private var memory = os_proc_available_memory()

    var body: some View {
        HStack(spacing: 0) {
            VStack(spacing: 16) {
                if let icon = appIcon() {
                    Image(uiImage: icon).resizable().frame(width: 96, height: 96).clipShape(RoundedRectangle(cornerRadius: 22))
                }
                Text((info("CFBundleDisplayName") as? String) ?? "Game").font(.title.weight(.bold)).multilineTextAlignment(.center)
                Text("Version \((info("CFBundleShortVersionString") as? String) ?? "")").font(.callout).foregroundStyle(.secondary)
                playButton
            }
            .padding(24)
            .frame(maxWidth: .infinity)
            Form {
                ForEach(m.settings) { SettingRow(s: $0, m: m) }
                Section {
                    HStack {
                        Text("Memory available")
                        Spacer()
                        Text(ByteCountFormatter.string(fromByteCount: Int64(memory), countStyle: .memory)).monospacedDigit().foregroundStyle(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity)
        }
        .preferredColorScheme(.dark)
        .task {
            while !Task.isCancelled {
                memory = os_proc_available_memory()
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    @ViewBuilder var playButton: some View {
        let button = Button(action: play) { Text("Play").font(.title3.weight(.semibold)).frame(maxWidth: 220) }.controlSize(.large)
        button.buttonStyle(.borderedProminent)
    }

    private func appIcon() -> UIImage? {
        if let i = UIImage(named: "AppIcon") { return i }
        guard let icons = info("CFBundleIcons") as? [String: Any], let primary = icons["CFBundlePrimaryIcon"] as? [String: Any],
              let files = primary["CFBundleIconFiles"] as? [String], let last = files.last else { return nil }
        return UIImage(named: last)
    }
}

// Shows the launcher over the root view controller and calls done once the settings are in the environment; false (done is not called) when there is no launcher
@_cdecl("dm_show_launcher")
public func dmShowLauncher(_ viewController: UnsafeMutableRawPointer, _ done: @convention(c) () -> Void) -> Bool {
    if ProcessInfo.processInfo.environment["DM_LAUNCHER"] == "0" { fputs("launcher: off (DM_LAUNCHER=0)\n", stderr); return false }
    guard let url = Bundle.main.resourceURL?.appendingPathComponent("dm/launcher.json"), let data = try? Data(contentsOf: url) else { return false }
    guard let file = try? JSONDecoder().decode(SettingsFile.self, from: data), !file.settings.isEmpty else { fputs("[RED] launcher: dm/launcher.json cannot be read; starting the game\n", stderr); return false }
    let parent = Unmanaged<UIViewController>.fromOpaque(viewController).takeUnretainedValue()
    let model = LauncherModel(file.settings)
    var host: UIViewController?
    let view = LauncherView(m: model) {
        guard let h = host else { return }
        host = nil
        model.apply()
        h.dismiss(animated: false) { done() }
    }
    let h = UIHostingController(rootView: view)
    h.modalPresentationStyle = .fullScreen
    host = h
    parent.present(h, animated: false)
    fputs("launcher: \(file.settings.count) settings shown\n", stderr)
    return true
}
