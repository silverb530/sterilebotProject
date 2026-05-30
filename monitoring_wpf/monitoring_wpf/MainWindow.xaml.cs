using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Windows;
using monitoring_wpf.Services;
using monitoring_wpf.Views;

namespace monitoring_wpf
{
    public partial class MainWindow : Window
    {
        private readonly FlaskClient _flask = new("http://localhost:5000");
        private readonly PythonProcessManager _procMgr = new();

        // 인증된 연구원 정보 (한글 이름)
        public static string AuthName { get; set; } = "";
        public static string AuthRole { get; set; } = "";

        // 영문 캘리브 파일명 (name_map.json 으로 변환된 결과)
        public static string CalibName { get; set; } = "";

        public MainWindow()
        {
            InitializeComponent();
            // 주의: KillZombiePythons() 는 호출 안 함 — app.py 같은 다른 Python 도
            //       같이 죽이는 부작용이 있어서 사용 안 함.
            //       좀비가 쌓이면 PowerShell 에서 taskkill /F /IM python.exe 수동 사용.
            SetupFlask();

            // Wire navigation callbacks
            ViewFaceAuth.OnAuthComplete = OnAuthCompleted;
            ViewMain.OnDriveTest = () => Navigate("drivetest");
            ViewMain.OnStart = StartExperiment;
            ViewMain.OnExit = () => Application.Current.Shutdown();
            ViewDriveTest.OnBack = () => Navigate("main");
            ViewRunning.OnEmergencyStop = () => ViewRunning.SetEmergency(true);
            ViewRunning.OnResume = () => ViewRunning.SetEmergency(false);
            ViewRunning.OnExit = () =>
            {
                // 실험 종료: Zone_tracker, gesture_control 만 종료.
                // Learning_TWM(시선 트래킹) 은 계속 작동하므로 커서도 그대로.
                _procMgr.StopExperiment();
                Navigate("main");
            };

            Navigate("faceauth");
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

        // "시작" 클릭: 팝업에 영문 캘리브명 자동 채워짐 → 시선으로 시작 버튼 Dwell 클릭
        private void StartExperiment()
        {
            // 팝업 기본값으로 영문 캘리브명 전달
            var dlg = new StartupDialog(CalibName) { Owner = this };
            bool? ok = dlg.ShowDialog();
            if (ok != true) return;

            _procMgr.StartAll(dlg.UserName, dlg.UseRobot, dlg.RobotIp, dlg.RobotPort);
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
            _procMgr.StopAll();
            CursorRestorer.RestoreSystemCursors();
            _flask.StopPolling();
            _flask.Dispose();
            base.OnClosed(e);
        }
    }
}