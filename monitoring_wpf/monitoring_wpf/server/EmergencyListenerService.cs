using System;
using System.Net;                   // IPAddress 사용
using System.Net.Http;
using System.Net.Sockets;           // TcpListner. TcpClient 사용
using System.Text;
using System.Text.Json;
using System.Threading;             // CancellationTokenSource 사용
using System.Threading.Tasks;       // Task(비동기 처리) 사용


namespace monitoring_wpf.service
{
    // IDisposable : 이 클래스가 끝날 때 리소스(소켓 등)을 정리해주는 인터페이스
    public class EmergencyListenerService : IDisposable
    {
        // ── 포트 설정 ────────────────────────────────────
        // wpf가 라파 신호 받을 포트
        private const int LISTEN_PORT = 9005;
        // 라파 IP
        //private const string PI_IP = "192.168.0.74";
        // 라파 소켓 서버 포트
        //private const int PI_PORT = 9002;
        // 마이코봇 라파 IP
        private const string PI_IP = "192.168.0.32";
        // 마이코봇 라파 소켓 서버 포트
        private const int PI_PORT = 9002;
        // 서보 서버 포트
        private const int SERVO_PORT = 9003;
        // Flask 서버 주소 (비상 이력 적재용)
        private const string FLASK_URL = "http://localhost:5000";


        // ── 내부 상태 ────────────────────────────────────
        // TcpListener : 라파가 보내는 신호를 기다리는 서버 소켓 (? = null 허용)
        private TcpListener? _listener;

        // CancellationTokenSource : 백그라운드 루프를 중단시킬 때 사용하는 취소 신호
        private CancellationTokenSource _cts = new();

        // Flask API 호출용 HTTP 클라이언트
        private static readonly HttpClient _http = new();

        // WPF가 발생시킨 비상 로그 ID (해제 시 사용, Pi 발생이면 null)
        private int? _emergencyLogId = null;
        // 환기 중 가스값 받기
        public event Action<int>? VentGasUpdate;
        // 환기 완료 시 main에 알려줌
        public event Action? VentDone;

        // ── 이벤트 ─────────────────────────────────────
        // 비상 상태가 바뀔 때 main에 알려줌
        // true = 비상 , false = 비상 해제
        // ?를 쓰면 구독자가 없을 때 호출해도 에러 안남
        public event Action<bool>? EmergencyStateChanged;
        public event Action<string>? EmergencySourceChanged;  // ★ 비상 원인 이벤트
        public event Action? DoorUnlocked;     // 외부문 잠금 안내


        // ── Pi 수신 리스너 ─────────────────────────────────
        public void Start()
        {
            // 모든 IP에서 오는 신호를 LISTEN_PORT로 받겠다고 선언
            _listener = new TcpListener(IPAddress.Any, LISTEN_PORT);

            // 연결 대기 시작
            _listener.Start();

            // ListenLoop를 백그라운드 스레드에서 실행 (UI 안 멈추게)
            // _cts.Token : 나중에 Stop() 호출하면 이 루프도 같이 종료됨
            Task.Run(ListenLoop, _cts.Token);

            System.Diagnostics.Debug.WriteLine($"[Emergency] 리스너 시작 - 포트 {LISTEN_PORT}");

        }

        // 라파 연결을 계속 기다리는 루프(비동기)
        private async Task ListenLoop()
        {
            while (!_cts.Token.IsCancellationRequested)
            {
                try
                {
                    // 라파가 연결해올 때까지 기다림(비동기라 UI 안멈춤)
                    var client = await _listener!.AcceptTcpClientAsync(_cts.Token);

                    // 연결 온 클라이언트를 별도 스레드에서 처리
                    // _ = 반환값 무시(경고 방지용)
                    _ = Task.Run(() => HandleClient(client));
                }
                catch (OperationCanceledException) { break; }   //정상종료시
                catch { /* 예외 무시하고 대기 */}
            }
        }

        // 라파로부터 실제 데이터를 읽고 처리하는 함수
        private void HandleClient(TcpClient client)
        {
            try
            {
                var buf = new byte[1024];

                // 스트림에서 데이터 읽기, n=실제 읽은 바이트 수
                int n = client.GetStream().Read(buf, 0, buf.Length);

                // 바이트 -> 문자열 변환 후 앞디 공백/줄바꿈 제거
                var msg = Encoding.UTF8.GetString(buf, 0, n).Trim();

                System.Diagnostics.Debug.WriteLine($"[Emergency] 수신: {msg}");

                // 받은 메시지에 따라 이벤트 발생
                if (msg.StartsWith("EMERGENCY:") || msg == "EMERGENCY")
                {
                    // source 파싱: "EMERGENCY:GAS_SENSOR" → "GAS_SENSOR"
                    string source = msg.Contains(":") ? msg.Split(':')[1] : "WPF_BUTTON";
                    EmergencyStateChanged?.Invoke(true);
                    EmergencySourceChanged?.Invoke(source);  // ★ source 전달
                }
                else if (msg == "EMERGENCY_END") EmergencyStateChanged?.Invoke(false);
                else if (msg.StartsWith("VENT_GAS:"))
                {
                    if (int.TryParse(msg.Substring(9), out int gas))  // "VENT_GAS" 글자 빼고 가스 농도만
                        VentGasUpdate?.Invoke(gas);
                }
                else if (msg == "VENT_DONE") VentDone?.Invoke();   // 환기 완료
                else if (msg == "DOOR_UNLOCKED") DoorUnlocked?.Invoke();   // 문 안잠김
            }
            finally
            {
                client.Dispose();
            }
        }

        public static async Task SendToPiAsync(string msg)
        {
            try
            {
                // 라파에 TCP연결
                using var client = new TcpClient();

                // ConnectAsync : 비동기 연결
                // WaitAsync(2초) : 2초 안에 연결 안되면 포기
                await client.ConnectAsync(PI_IP, PI_PORT).WaitAsync(TimeSpan.FromSeconds(2));

                // 문자열 -> 바이트 변환 후 전송
                var data = Encoding.UTF8.GetBytes(msg + "\n");
                await client.GetStream().WriteAsync(data);

                System.Diagnostics.Debug.WriteLine($"[Emergency] Pi 전송: {msg}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Emergency] Pi 전송 실패: {ex.Message}");
            }
        }

        // WPF 비상 버튼 클릭 시 Flask에 비상 발생 이력 적재
        // triggerSource = WPF_BUTTON....EME_BUTTON
        public async Task HisLoadStartAsync(string triggerSource, int researcherId = 0)
        {
            try
            {
                // triggerSource를 JSON으로 직렬화
                var payload = JsonSerializer.Serialize(new
                {
                    trigger_source = triggerSource,
                    researcher_id = researcherId == 0 ? (int?)null : researcherId  // 0이면 null로
                });
                // UTF-8 JSON 바디 생성 content-type은 application/json
                var content = new StringContent(payload, Encoding.UTF8, "application/json");
                // url 호출 -> 인서트 
                var response = await _http.PostAsync($"{FLASK_URL}/api/emergency/start", content);

                // 응답에 대한 바디 파싱 => { "ok": true, "id": 5 } 이렇게 옴
                var body = await response.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);

                if (doc.RootElement.GetProperty("ok").GetBoolean())
                {
                    // 생성된 행의 ID 저장 → 나중에 ReportEndAsync에서 해제 시 사용
                    _emergencyLogId = doc.RootElement.GetProperty("id").GetInt32();
                    System.Diagnostics.Debug.WriteLine($"[Emergency] Flask 적재 완료 ID={_emergencyLogId}");
                }
            }
            catch (Exception ex)
            {
                // Flask가 꺼져있거나 네트워크 문제 → 비상 화면/부저는 계속 정상 동작
                System.Diagnostics.Debug.WriteLine($"[Emergency] Flask 적재 실패: {ex.Message}");
            }
        }

        public async Task HisLoadEndAsync(string resolvedBy)
        {
            // _emergencyLogId가 null이면 Pi가 발생시킨 비상
            // Pi는 EMERGENCY_END 수신 시 자체적으로 Flask 해제 업데이트를 처리하므로
            // WPF에서 중복 호출할 필요 없음
            if (_emergencyLogId == null)
            {
                System.Diagnostics.Debug.WriteLine("[Emergency] Pi 발생 비상 → Pi가 Flask 해제 처리");
                return;
            }

            try
            {
                // 해제할 로그 ID와 해제 주체를 JSON으로 직렬화
                // { "id": 5, "resolved_by": "WPF_RESET" }
                var payload = JsonSerializer.Serialize(
                    new { id = _emergencyLogId, resolved_by = resolvedBy });

                // UTF-8 JSON 바디 생성
                var content = new StringContent(payload, Encoding.UTF8, "application/json");

                // Flask /api/emergency/end 호출
                // → emergency_log의 resolved_at, duration_sec, resolved_by UPDATE
                await _http.PostAsync($"{FLASK_URL}/api/emergency/end", content);

                System.Diagnostics.Debug.WriteLine($"[Emergency] Flask 해제 완료 ID={_emergencyLogId}");

                // 다음 비상 발생을 위해 ID 초기화
                _emergencyLogId = null;
            }
            catch (Exception ex)
            {
                // Flask 꺼져있어도 비상 해제 자체는 정상 동작
                System.Diagnostics.Debug.WriteLine($"[Emergency] Flask 해제 실패: {ex.Message}");
            }
        }

        // Pi 발생 비상에 researcher_id 업데이트
        public async Task UpdateResearcherAsync(int researcherId)
        {
            try
            {
                var payload = JsonSerializer.Serialize(new { researcher_id = researcherId });
                var content = new StringContent(payload, Encoding.UTF8, "application/json");
                await _http.PostAsync($"{FLASK_URL}/api/emergency/update_researcher", content);
                System.Diagnostics.Debug.WriteLine($"[Emergency] researcher_id 업데이트: {researcherId}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Emergency] researcher_id 업데이트 실패: {ex.Message}");
            }
        }

        // 서보 서버(도어 제어)에 명령 전송
        // msg : "EXP_START" | "LOCK_OPEN" | "LOCK_CLOSE" | "DOOR_OPEN" | "DOOR_CLOSE" | "EXP_END"
        public static async Task SendToServoAsync(string msg)
        {
            try
            {
                using var client = new TcpClient();

                // 2초 안에 연결 안 되면 포기 (Pi 꺼져있어도 WPF 안 멈춤)
                await client.ConnectAsync(PI_IP, SERVO_PORT).WaitAsync(TimeSpan.FromSeconds(2));

                // 문자열 → 바이트 변환 후 전송
                var data = Encoding.UTF8.GetBytes(msg + "\n");
                await client.GetStream().WriteAsync(data);

                System.Diagnostics.Debug.WriteLine($"[Servo] 전송: {msg}");
            }
            catch (Exception ex)
            {
                // Pi 꺼져있거나 네트워크 문제 → 서보 안 움직이지만 WPF는 정상 동작
                System.Diagnostics.Debug.WriteLine($"[Servo] 전송 실패: {ex.Message}");
            }
        }

        // IDisposable 구현 - 자원정리
        public void Dispose()
        {
            _cts.Cancel();          // 백그라운드 루프에 종료 신호 보내기
            _listener?.Stop();      // 소켓 서버 닫기
        }
    }
}