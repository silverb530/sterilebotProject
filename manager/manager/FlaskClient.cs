using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace SterileBot.Calibration
{
    // ── Flask에서 받아오는 상태 모델 ──────────────────────────────
    public class FlaskState
    {
        [JsonPropertyName("fsm")]     public string Fsm     { get; set; } = "IDLE";
        [JsonPropertyName("ear")]     public double Ear     { get; set; }
        [JsonPropertyName("dwell")]   public double Dwell   { get; set; }
        [JsonPropertyName("gripper")] public string Gripper { get; set; } = "open";
        [JsonPropertyName("robot")]   public RobotCoords Robot { get; set; } = new();
        [JsonPropertyName("params")]  public FlaskParams Params { get; set; } = new();
    }

    public class RobotCoords
    {
        [JsonPropertyName("x")]  public double X  { get; set; }
        [JsonPropertyName("y")]  public double Y  { get; set; }
        [JsonPropertyName("z")]  public double Z  { get; set; }
        [JsonPropertyName("rx")] public double Rx { get; set; }
        [JsonPropertyName("ry")] public double Ry { get; set; }
        [JsonPropertyName("rz")] public double Rz { get; set; }
    }

    public class FlaskParams
    {
        [JsonPropertyName("ear_threshold")]  public double EarThreshold { get; set; } = 0.20;
        [JsonPropertyName("ear_ms")]         public int    EarMs        { get; set; } = 150;
        [JsonPropertyName("dwell_sec")]      public double DwellSec     { get; set; } = 1.5;
        [JsonPropertyName("dwell_radius")]   public int    DwellRadius  { get; set; } = 30;
        [JsonPropertyName("double_blink_sec")] public double DoubleBlinkSec { get; set; } = 0.5;
        [JsonPropertyName("safe_radius")]    public int    SafeRadius   { get; set; } = 260;
        [JsonPropertyName("safe_z")]         public int    SafeZ        { get; set; } = 200;
        [JsonPropertyName("grip_speed")]     public int    GripSpeed    { get; set; } = 10;
        [JsonPropertyName("move_speed")]     public int    MoveSpeed    { get; set; } = 30;
    }

    // ── Flask API 클라이언트 ──────────────────────────────────────
    public class FlaskClient : IDisposable
    {
        private readonly HttpClient _http;
        private readonly string _base;
        private CancellationTokenSource? _cts;

        // 이벤트: 상태 업데이트 / 연결 성공 / 연결 오류
        public event Action<FlaskState>? StateUpdated;
        public event Action? Connected;
        public event Action<string>? ConnectionError;

        public bool IsConnected { get; private set; }

        public FlaskClient(string baseUrl = "http://localhost:5000")
        {
            _base = baseUrl.TrimEnd('/');
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
        }

        // ── 폴링 시작 (500ms마다 /api/state GET) ─────────────────
        public void StartPolling(int intervalMs = 500)
        {
            _cts = new CancellationTokenSource();
            _ = PollLoopAsync(_cts.Token, intervalMs);
        }

        public void StopPolling() => _cts?.Cancel();

        private async Task PollLoopAsync(CancellationToken ct, int intervalMs)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var json = await _http.GetStringAsync($"{_base}/api/state", ct);
                    var state = JsonSerializer.Deserialize<FlaskState>(json)!;
                    if (!IsConnected) { IsConnected = true; Connected?.Invoke(); }
                    StateUpdated?.Invoke(state);
                }
                catch (Exception ex)
                {
                    if (IsConnected) { IsConnected = false; ConnectionError?.Invoke(ex.Message); }
                }
                try { await Task.Delay(intervalMs, ct); } catch { }
            }
        }

        // ── REST API 호출 메서드 ──────────────────────────────────

        // 로봇 이동
        public Task MoveAsync(double x, double y, double z,
            double rx = 0, double ry = 0, double rz = 0, int speed = 30)
            => PostAsync("/api/move", new { x, y, z, rx, ry, rz, speed });

        // 홈 복귀
        public Task GoHomeAsync()
            => PostAsync("/api/home", new { });

        // 그리퍼
        public Task SetGripperAsync(bool open)
            => PostAsync("/api/gripper", new { state = open ? "open" : "closed" });

        // FSM 변경 (긴급정지 등)
        public Task SetFsmAsync(string fsm)
            => PostAsync("/api/fsm", new { state = fsm });

        // 파라미터 적용
        public Task ApplyParamsAsync(FlaskParams p)
            => PostAsync("/api/params", p);

        // 캘리브레이션 포인트 저장
        public Task SaveCalibPointAsync(int marker, int px, int py, double mmX, double mmY)
            => PostAsync("/api/calib", new { marker, px, py, mm_x = mmX, mm_y = mmY });

        // 캘리브레이션 초기화
        public Task ResetCalibAsync()
            => _http.DeleteAsync($"{_base}/api/calib");

        // ── 내부 헬퍼 ─────────────────────────────────────────────
        private async Task PostAsync(string path, object body)
        {
            try
            {
                var content = new StringContent(
                    JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
                await _http.PostAsync($"{_base}{path}", content);
            }
            catch (Exception ex)
            {
                ConnectionError?.Invoke($"POST {path} 실패: {ex.Message}");
            }
        }

        public void Dispose()
        {
            _cts?.Cancel();
            _http.Dispose();
        }
    }
}
