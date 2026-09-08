import SwiftUI

/// Short LCD readings use native paths; labels and longer text remain ordinary type.
struct SegmentDisplay: View {
    let text: String
    var height: CGFloat = 20
    var color: Color = ClusterTheme.lcd
    var body: some View {
        Canvas { context, size in
            SevenSegment.draw(text, in: CGRect(origin: .zero, size: size), color: color, context: context)
        }
        .frame(width: SevenSegment.width(text, height: height), height: height)
        .accessibilityLabel(text)
    }
}

enum SevenSegment {
    private static let digits: [Character: Set<Int>] = [
        "0": [0, 1, 2, 3, 4, 5], "1": [1, 2], "2": [0, 1, 6, 4, 3],
        "3": [0, 1, 2, 3, 6], "4": [5, 6, 1, 2], "5": [0, 5, 6, 2, 3],
        "6": [0, 5, 4, 3, 2, 6], "7": [0, 1, 2], "8": [0, 1, 2, 3, 4, 5, 6],
        "9": [0, 1, 2, 3, 5, 6], "-": [6], "—": [6]
    ]
    private static func advance(_ character: Character) -> CGFloat {
        character == "." || character == ":" ? 0.24 : 0.68
    }
    static func width(_ text: String, height: CGFloat) -> CGFloat {
        max(0, text.reduce(0) { $0 + advance($1) } - 0.08) * height
    }
    static func draw(_ text: String, in rect: CGRect, color: Color, context: GraphicsContext) {
        let height = min(rect.height, rect.width / max(width(text, height: 1), 0.1))
        var x = rect.midX - width(text, height: height) / 2
        let y = rect.midY - height / 2
        let segments: [(CGPoint, CGPoint)] = [
            (.init(x: 0.10, y: 0.05), .init(x: 0.50, y: 0.05)),
            (.init(x: 0.55, y: 0.10), .init(x: 0.55, y: 0.45)),
            (.init(x: 0.55, y: 0.55), .init(x: 0.55, y: 0.90)),
            (.init(x: 0.10, y: 0.95), .init(x: 0.50, y: 0.95)),
            (.init(x: 0.05, y: 0.55), .init(x: 0.05, y: 0.90)),
            (.init(x: 0.05, y: 0.10), .init(x: 0.05, y: 0.45)),
            (.init(x: 0.10, y: 0.50), .init(x: 0.50, y: 0.50))
        ]
        for character in text {
            if character == "." || character == ":" {
                for level: CGFloat in character == ":" ? [0.3, 0.7] : [0.95] {
                    context.fill(Path(CGRect(x: x + height * 0.03, y: y + height * (level - 0.05), width: height * 0.10, height: height * 0.10)), with: .color(color))
                }
            } else {
                let lit = digits[character] ?? []
                for (index, endpoints) in segments.enumerated() {
                    let a = CGPoint(x: x + endpoints.0.x * height, y: y + endpoints.0.y * height)
                    let b = CGPoint(x: x + endpoints.1.x * height, y: y + endpoints.1.y * height)
                    let dx = b.x - a.x, dy = b.y - a.y, length = hypot(dx, dy)
                    let ux = dx / length, uy = dy / length, t = height * 0.047
                    var path = Path()
                    path.move(to: a)
                    path.addLine(to: .init(x: a.x + ux * t - uy * t, y: a.y + uy * t + ux * t))
                    path.addLine(to: .init(x: b.x - ux * t - uy * t, y: b.y - uy * t + ux * t))
                    path.addLine(to: b)
                    path.addLine(to: .init(x: b.x - ux * t + uy * t, y: b.y - uy * t - ux * t))
                    path.addLine(to: .init(x: a.x + ux * t + uy * t, y: a.y + uy * t - ux * t))
                    path.closeSubpath()
                    context.fill(path, with: .color(color.opacity(lit.contains(index) ? 1 : 0.035)))
                }
            }
            x += advance(character) * height
        }
    }
}
