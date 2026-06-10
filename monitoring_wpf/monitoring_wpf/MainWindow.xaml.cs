using monitoring_wpf.service;
using monitoring_wpf.Services;
using monitoring_wpf.Views;
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Runtime.ConstrainedExecution;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;

namespace monitoring_wpf
{
    public partial class MainWindow : Window
    {
        private readonly FlaskClient _flask = new("http://localhost:5000");
        private readonly PythonProcessManager _procMgr = new();

        // 비상상황 이벤트 리스너
        private readonly EmergencyListenerService _emergencyService = new();
        // 환기 이벤트
        private monitoring_wpf.Views.VentingWindow? _ventWindow;

        private bool _resumeDialogShowing = false;   // 재개 다이얼로그 중복 방지

        // 인증된 연구원 정보 (한글 이름)
        public static string AuthName { get; set; } = "";
        public static string AuthRole { get; set; } = "";
        public static int AuthId { get; set; } = 0;

        // 영문 캘리브 파일명 (name_map.json 으로 변환된 결과)
        public static string CalibName { get; set; } = "";

        // ★ 대피 음성 재생 — myCobot Pi HTTP
        private static readonly HttpClient _alarmHttp = new() { Timeout = TimeSpan.FromSeconds(3) };
        private const string PiAlarmBase = "http://192.168.0.32:5001";

        public MainWindow()
        {
            InitializeComponent();
            // 주의: KillZombiePythons() 는 호출 안 함 — app.py 같은 다른 Python 도
            //       같이 죽이는 부작용이 있어서 사용 안 함.
            //       좀비가 쌓이면 PowerShell 에서 taskkill /F /IM python.exe 수동 사용.
            SetupFlask();
            _procMgr.StartFlaskServer();      // Flask 서버 자동 시작 (app.py)
            _procMgr.StartFallDetection();    // ★ 쓰러짐 감지 백그라운드 실행

            // Wire navigation callbacks
            ViewFaceAuth.OnAuthComplete = OnAuthCompleted;
            ViewMain.OnDriveTest = () => Navigate("drivetest");
            ViewMain.OnStart = StartExperiment;
            ViewMain.OnExit = () =>
            {
                // 로그아웃: 모든 Python 프로세스 종료 후 Flask만 재시작
                _procMgr.StopAll();
                _procMgr.StartFlaskServer();

                // 인증 정보 초기화
                AuthName = "";
                AuthRole = "";
                AuthId = 0;
                CalibName = "";

                Navigate("faceauth");
            };
            ViewRunning.OnExit = () =>
            {
                // 이미 환기 중이면 무시 (중복 클릭 방지)
                if (_ventWindow != null) return;

                // Pi에 환기 시작 명령
                _ = EmergencyListenerService.SendToPiAsync("VENT_START");

                // 환기 알림창 (모달) — VENT_DONE 또는 강제종료 시 닫힘
                _ventWindow = new monitoring_wpf.Views.VentingWindow { Owner = this };
                _ventWindow.ShowDialog();   // 창 닫힐 때까지 여기서 대기 (모달)

                // 창이 닫혔으면 → 실험 종료 진행
                _ventWindow = null;
                // 실험 종료: Zone_tracker, gesture_control 만 종료.
                // Learning_TWM(시선 트래킹) 은 계속 작동하므로 커서도 그대로.
                _procMgr.StopExperiment();
                // Pi 로그 초기화 (다음 실험을 위해)
                _ = new HttpClient { Timeout = TimeSpan.FromSeconds(3) }
                    .GetAsync("http://192.168.0.32:5001/clear_log");
                Navigate("main");
            };

            ViewDriveTest.OnBack = () => Navigate("main");

            // ★ 비상 버튼 클릭 시 음성 재생 추가
            ViewRunning.OnEmergencyStop = () =>
            {
                ViewRunning.SetEmergency(true);
                _ = EmergencyListenerService.SendToPiAsync("EMERGENCY");
                _ = _emergencyService.HisLoadStartAsync("WPF_BUTTON", MainWindow.AuthId);
                _ = PlayAlarmAsync();          // ★ 대피 음성 재생
                _ = SendToSecurityAsync();     // ★ 보안실 비상 알림
            };

            // ★ 비상 해제 시 음성 중단 추가
            ViewRunning.OnResume = () =>
            {
                ViewRunning.SetEmergency(false);
                _ = EmergencyListenerService.SendToPiAsync("EMERGENCY_END");
                _ = _emergencyService.HisLoadEndAsync("WPF_RESET");
                _ = StopAlarmAsync();              // ★ 대피 음성 중단
                _ = SendClearToSecurityAsync();    // ★ 보안실 해제 알림

                ShowResumeDialog();   // 계속/종료 큰 버튼 창
            };

            // ★ 비상 원인 수신 시 로그 출력
            _emergencyService.EmergencySourceChanged += source =>
            {
                string sourceName = source switch
                {
                    "GAS_SENSOR" => "가스 누출",
                    "EME_BUTTON" => "비상 버튼",
                    "FALL_DOWN" => "쓰러짐 감지",
                    "WPF_BUTTON" => "WPF 버튼",
                    _ => source
                };
                Dispatcher.Invoke(() =>
                    System.Diagnostics.Debug.WriteLine($"[비상 원인] {sourceName}"));
            };

            // ★ Pi 발생 비상 시에도 음성 재생
            _emergencyService.EmergencyStateChanged += isEmergency =>
            {
                Dispatcher.Invoke(() => ViewRunning.SetEmergency(isEmergency));
                if (isEmergency)
                {
                    _ = _emergencyService.UpdateResearcherAsync(MainWindow.AuthId);
                    _ = PlayAlarmAsync();              // ★ 대피 음성 재생
                    _ = SendToSecurityAsync();         // ★ 보안실 비상 알림
                }
                else
                {
                    _ = StopAlarmAsync();              // ★ 대피 음성 중단
                    _ = SendClearToSecurityAsync();    // ★ 보안실 해제 알림

                    Dispatcher.Invoke(ShowResumeDialog);   // 계속/종료 큰 버튼 창
                }
            };

            // 환기 완료 신호 받으면 알림창 닫기 → OnExit의 ShowDialog가 반환됨
            _emergencyService.VentDone += () =>
            {
                Dispatcher.Invoke(() => _ventWindow?.Close());
            };
            // 환기 중 가스값 받으면 알림창에 표시
            _emergencyService.VentGasUpdate += gas =>
            {
                Dispatcher.Invoke(() => _ventWindow?.UpdateGas(gas));
            };

            // 외부문 미잠금 시 안내
            _emergencyService.DoorUnlocked += () =>
            {
                Dispatcher.Invoke(() =>
                    MessageBox.Show(
                        "외부문이 잠겨있지 않습니다.\n\n시약관에 접근하려면 먼저 외부문을 잠가주세요.",
                        "외부문 잠금 필요",
                        MessageBoxButton.OK,
                        MessageBoxImage.Warning));
            };
            _emergencyService.Start();

            Navigate("faceauth");
        }

        // 비상 해제 후 계속/종료 선택 창
        private void ShowResumeDialog()
        {
            if (_resumeDialogShowing) return;   // 중복 방지
            _resumeDialogShowing = true;

            var dlg = new monitoring_wpf.Views.ResumeDialog { Owner = this };
            dlg.ShowDialog();

            _resumeDialogShowing = false;

            if (!dlg.ContinueExperiment)
            {
                // 종료 → 홈 복귀 + 실험 종료 + 메인
                _ = new HttpClient { Timeout = TimeSpan.FromSeconds(10) }
                    .GetAsync("http://192.168.0.32:5001/home");
                _procMgr.StopExperiment();
                Navigate("main");
            }
            // 계속 → 창만 닫힘 (HOME 응시로 재개)
        }

        // ★ 대피 음성 재생 요청
        private async Task PlayAlarmAsync()
        {
            try
            {
                await _alarmHttp.PostAsync($"{PiAlarmBase}/play_alarm", null);
                System.Diagnostics.Debug.WriteLine("[Alarm] 재생 요청 성공");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Alarm] 재생 실패: {ex.Message}");
            }
        }

        // ★ 대피 음성 중단 요청
        private async Task StopAlarmAsync()
        {
            try
            {
                await _alarmHttp.PostAsync($"{PiAlarmBase}/stop_alarm", null);
                System.Diagnostics.Debug.WriteLine("[Alarm] 중단 요청 성공");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Alarm] 중단 실패: {ex.Message}");
            }
        }

        // ★ 보안실 비상 UDP 브로드캐스트 (포트 9998)
        private async Task SendToSecurityAsync()
        {
            try
            {
                using var udp = new UdpClient();
                udp.EnableBroadcast = true;
                var msg = Encoding.UTF8.GetBytes(
                  $"{{\"type\":\"emergency\",\"ts\":\"{DateTime.Now:yyyy-MM-dd HH:mm:ss}\"}}");
                await udp.SendAsync(msg, msg.Length, "255.255.255.255", 9998);
                System.Diagnostics.Debug.WriteLine("[보안실] 비상 UDP 전송 완료");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[보안실] 비상 전송 실패: {ex.Message}");
            }
        }

        private async Task SendClearToSecurityAsync()
        {
            try
            {
                using var udp = new UdpClient();
                udp.EnableBroadcast = true;
                var msg = Encoding.UTF8.GetBytes("{\"type\":\"clear\"}");
                await udp.SendAsync(msg, msg.Length, "255.255.255.255", 9998);
                System.Diagnostics.Debug.WriteLine("[보안실] 해제 UDP 전송 완료");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[보안실] 해제 전송 실패: {ex.Message}");
            }
        }

        // 얼굴 인증 통과 직후:
        //  1) 인증 이름(한글) → 영문 캘리브명 매핑
        //  2) Learning_TWM 즉시 시작 → 시선 커서 활성화
        //  3) 메인 화면 전환
        private void OnAuthCompleted()
        {
            CalibName = MapAuthNameToCalibName(AuthName);

            if (!string.IsNullOrEmpty(CalibName))
            {
                _procMgr.StartTracking(CalibName);
                _procMgr.StartGesture();
            }
            else
            {
                MessageBox.Show(
                    $"'{AuthName}' 에 매핑된 캘리브레이션 파일명이 없습니다.\n" +
                    "name_map.json 을 확인하거나 시작 시 직접 입력하세요.",
                    "안내", MessageBoxButton.OK, MessageBoxImage.Information);
            }

            Navigate("main");
        }

        // name_map.json 을 읽어 한글 이름 → 영문 캘리브명 변환
        private string MapAuthNameToCalibName(string authName)
        {
            if (string.IsNullOrWhiteSpace(authName)) return "";

            try
            {
                // 1순위: 실행 파일 옆 (bin\Debug\... 에 복사된 경우)
                string mapPath = Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory, "name_map.json");
                if (!File.Exists(mapPath))
                {
                    // 2순위: 현재 작업 폴더
                    mapPath = "name_map.json";
                }
                if (!File.Exists(mapPath)) return "";

                string json = File.ReadAllText(mapPath);
                var map = JsonSerializer.Deserialize<Dictionary<string, string>>(json);
                if (map != null && map.TryGetValue(authName, out string? calib))
                {
                    return calib ?? "";
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"name_map.json 읽기 실패: {ex.Message}");
            }
            return "";
        }

        // "시작" 클릭: 팝업 없이 자동 시작
        //  - 사용자 이름: 얼굴 인증에서 매핑된 CalibName 사용
        //  - 로봇: 항상 연결 (useRobot = true)
        private void StartExperiment()
        {
            string userName = string.IsNullOrEmpty(CalibName) ? "minjun" : CalibName;

            // 실험 시작 시 서보 초기화 (잠금장치 잠금)
            // Pi의 door_server.py가 EXP_START 수신 → experiment_start() 실행
            _ = EmergencyListenerService.SendToServoAsync("EXP_START");  // ◀ 추가

            _procMgr.StartAll(userName, useRobot: true, robotIp: "192.168.0.32", robotPort: 5001);
            Navigate("running");
        }

        private void Navigate(string view)
        {
            ViewFaceAuth.Visibility = view == "faceauth" ? Visibility.Visible : Visibility.Collapsed;
            ViewMain.Visibility = view == "main" ? Visibility.Visible : Visibility.Collapsed;
            ViewDriveTest.Visibility = view == "drivetest" ? Visibility.Visible : Visibility.Collapsed;
            ViewRunning.Visibility = view == "running" ? Visibility.Visible : Visibility.Collapsed;
            if (view == "running") ViewRunning.SetEmergency(false);
        }

        private void SetupFlask()
        {
            _flask.StateUpdated += state => Dispatcher.Invoke(() =>
            {
                ViewMain.UpdateState(state);
                ViewRunning.UpdateState(state);
            });
            _flask.StartPolling(500);
        }

        protected override void OnClosed(EventArgs e)
        {
            _emergencyService.Dispose();
            _procMgr.StopAll();
            CursorRestorer.RestoreSystemCursors();
            _flask.StopPolling();
            _flask.Dispose();
            base.OnClosed(e);
        }
    }
}