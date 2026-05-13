using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace monitoring_wpf.Services
{
    public class GazeData
    {
        [JsonPropertyName("cx")] public int Cx { get; set; }
        [JsonPropertyName("cy")] public int Cy { get; set; }
        [JsonPropertyName("rx")] public int Rx { get; set; }
        [JsonPropertyName("ry")] public int Ry { get; set; }
    }

    public class RobotData
    {
        [JsonPropertyName("x")] public double X { get; set; }
        [JsonPropertyName("y")] public double Y { get; set; }
        [JsonPropertyName("z")] public double Z { get; set; }
        [JsonPropertyName("rx")] public double Rx { get; set; }
        [JsonPropertyName("ry")] public double Ry { get; set; }
        [JsonPropertyName("rz")] public double Rz { get; set; }
    }

    public class FlaskState
    {
        [JsonPropertyName("fsm")] public string Fsm { get; set; } = "IDLE";
        [JsonPropertyName("ear")] public double Ear { get; set; }
        [JsonPropertyName("gaze")] public GazeData Gaze { get; set; } = new();
        [JsonPropertyName("dwell")] public double Dwell { get; set; }
        [JsonPropertyName("robot")] public RobotData Robot { get; set; } = new();
        [JsonPropertyName("gripper")] public string Gripper { get; set; } = "open";
        [JsonPropertyName("gaze_enabled")] public bool GazeEnabled { get; set; } = true;
    }

    public class FlaskClient : IDisposable
    {
        private readonly HttpClient _http;
        private readonly string _base;
        private CancellationTokenSource? _cts;

        public event Action<FlaskState>? StateUpdated;
        public event Action? Connected;
        public event Action<string>? ConnectionError;

        public FlaskClient(string baseUrl = "http://localhost:5000")
        {
            _base = baseUrl.TrimEnd('/');
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
        }

        public void StartPolling(int intervalMs = 500)
        {
            _cts = new CancellationTokenSource();
            _ = PollLoopAsync(_cts.Token, intervalMs);
        }

        public void StopPolling() => _cts?.Cancel();

        private async Task PollLoopAsync(CancellationToken ct, int intervalMs)
        {
            bool wasConnected = false;
            while (!ct.IsCancellationRequested)
            {
                FlaskState? state = null;
                bool fetchOk = false;
                try
                {
                    var json = await _http.GetStringAsync($"{_base}/api/state", ct);
                    state = JsonSerializer.Deserialize<FlaskState>(json);
                    fetchOk = state != null;
                }
                catch (Exception ex)
                {
                    if (wasConnected) { wasConnected = false; ConnectionError?.Invoke(ex.Message); }
                }

                if (fetchOk)
                {
                    if (!wasConnected) { wasConnected = true; Connected?.Invoke(); }
                    try { StateUpdated?.Invoke(state!); } catch { }
                }

                try { await Task.Delay(intervalMs, ct); } catch { }
            }
        }

        public Task SetFsmAsync(string fsm) => PostAsync("/api/fsm", new { state = fsm });
        public Task GoHomeAsync() => PostAsync("/api/home", new { });
        public Task SetGripperAsync(bool open) => PostAsync("/api/gripper", new { state = open ? "open" : "closed" });
        public Task ToggleGazeAsync() => PostAsync("/api/gaze_toggle", new { });

        private async Task PostAsync(string path, object body)
        {
            try
            {
                var content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
                await _http.PostAsync($"{_base}{path}", content);
            }
            catch { }
        }

        public void Dispose() { _cts?.Cancel(); _http.Dispose(); }
    }
}
