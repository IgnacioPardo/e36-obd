import Foundation

public struct GraphPoint: Identifiable, Sendable {
    public var id: Int64
    public var elapsed: Double
    public var value: Double
    public var segment: Int
}
public enum GraphSeries {
    /// Extrema per bucket, endpoints, and event samples survive reduction. Never connect across a gap.
    public static func points(_ samples: [RecordedSample], sensor: Sensor, budget: Int = 800,
                              preserving ids: Set<Int64> = []) -> [GraphPoint] {
        var result: [GraphPoint] = [], segment = 0
        var previous: RecordedSample?
        for sample in samples {
            guard sample.telemetry.validity == .populated, let value = sample.telemetry[sensor] else {
                previous = nil; segment += 1; continue
            }
            if let previous, previous.segment != sample.segment || sample.elapsed - previous.elapsed > 2 {
                segment += 1
            }
            result.append(GraphPoint(id: sample.id, elapsed: sample.elapsed, value: value, segment: segment))
            previous = sample
        }
        guard result.count > max(4, budget) else { return result }
        let bucketSize = max(1, Int(ceil(Double(result.count) / Double(max(2, budget / 2)))))
        var keep = Set<Int>()
        for index in result.indices {
            if index == 0 || index == result.count - 1 || ids.contains(result[index].id)
                || (index > 0 && result[index - 1].segment != result[index].segment)
                || (index + 1 < result.count && result[index + 1].segment != result[index].segment) { keep.insert(index) }
        }
        for start in stride(from: 0, to: result.count, by: bucketSize) {
            let indices = start..<min(start + bucketSize, result.count)
            if let minimum = indices.min(by: { result[$0].value < result[$1].value }) { keep.insert(minimum) }
            if let maximum = indices.max(by: { result[$0].value < result[$1].value }) { keep.insert(maximum) }
        }
        return keep.sorted().map { result[$0] }
    }
    public static func nearest(_ samples: [RecordedSample], elapsed: Double) -> RecordedSample? {
        guard !samples.isEmpty else { return nil }
        var low = 0, high = samples.count
        while low < high {
            let middle = (low + high) / 2
            if samples[middle].elapsed < elapsed { low = middle + 1 } else { high = middle }
        }
        if low == 0 { return samples[0] }
        if low == samples.count { return samples.last }
        return abs(samples[low].elapsed - elapsed) < abs(samples[low - 1].elapsed - elapsed) ? samples[low] : samples[low - 1]
    }
}
