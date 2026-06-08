using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Microsoft.Win32;

namespace LabSafetyManager
{
    public partial class MainWindow : System.Windows.Window
    {
        // ── 통제실 PC IP 설정 ───────────────────────────────────
        // 보안실 WPF는 로컬 카메라를 직접 열지 않는다.
        // 평소에는 대기 화면, 쓰러짐 감지 시에만 통제실에서 TCP로 영상이 온다.
        private const string CONTROL_PC_IP = "192.168.0.25"; // 통제실 PC IP
        private const int FALL_TCP_PORT = 9999;

        private readonly FallTcpClient _fallClient;
        private readonly Storyboard _flash;
        private readonly Storyboard _beacon;
        private readonly DispatcherTimer _clock = new();
        private readonly DispatcherTimer _standbyTimer = new(); // 대기 화면 시계
        private MediaPlayer? _siren;

        public ObservableCollection<LogEntry> Logs { get; } = new();

        private bool _emergencyActive;
        private bool _armed = true;
        private int _frameCount;

        public MainWindow()
        {
            InitializeComponent();
            LogListView.ItemsSource = Logs;

            _flash = (Storyboard)Resources["FlashStoryboard"];
            _beacon = (Storyboard)Resources["BeaconStoryboard"];

            // 시계
            ClockText.Text = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            _clock.Interval = TimeSpan.FromSeconds(1);
            _clock.Tick += (_, _) =>
                ClockText.Text = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            _clock.Start();

            TrySetupSiren();

            // ── FallTcpClient 초기화 ─────────────────────────────
            _fallClient = new FallTcpClient(CONTROL_PC_IP, FALL_TCP_PORT, 9998);
            _fallClient.EmergencyReceived += OnEmergencyReceived;
            _fallClient.FrameReceived += OnFallFrame;
            _fallClient.ConnectionChanged += OnFallConnectionChanged;

            // ── 카메라 콤보/로컬 카메라 비활성화 ──────────────────
            // 보안실은 카메라를 직접 열지 않으므로 UI 정리
            CameraCombo.IsEnabled = false;
            CameraCombo.Visibility = Visibility.Collapsed;

            Loaded += (_, _) =>
            {
                AddLog(LogLevel.Info, "보안실 시스템 시작");
                AddLog(LogLevel.Info, $"통제실 연결 시도 중 ({CONTROL_PC_IP}:{FALL_TCP_PORT})");
                ShowStandby();
                _fallClient.StartUdpListener();  // UDP 수신 대기 시작
                _fallClient.StartTcp();             // TCP 영상 상시 수신 시작
            };

            Closed += (_, _) =>
            {
                _fallClient.StopAll();
                _clock.Stop();
                _standbyTimer.Stop();
            };
        }

        // =================================================================
        // 대기 화면
        // =================================================================

        private void ShowStandby()
        {
            // VideoImage는 상시 표시 — 초기화 안 함
            CameraOverlay.Visibility = Visibility.Collapsed;  // 오버레이 숨김
            CameraBadge.Opacity = 0.3;

            SetCameraStatus(false, "대기");
            PersonStatusText.Text = "—";
            FallStatusText.Text = "—";
            SetLevel("정상", LogLevel.Info);
        }

        // =================================================================
        // FallTcpClient 이벤트 핸들러
        // =================================================================

        private void OnEmergencyReceived(object? sender, string timestamp)
        {
            Dispatcher.InvokeAsync(() =>
            {
                AddLog(LogLevel.Danger, $"쓰러짐 감지 수신 (통제실): {timestamp}");
                PersonStatusText.Text = "감지됨";
                FallStatusText.Text = "감지됨";
                SetLevel("비상", LogLevel.Danger);

                if (_armed && !_emergencyActive)
                    EnterEmergency(timestamp);
            });
        }

        private void OnFallFrame(object? sender, byte[] jpg)
        {
            // 비상 상황 여부와 관계없이 연결되면 영상 표시
            ShowFrame(jpg);
        }

        private void OnFallConnectionChanged(object? sender, bool connected)
        {
            Dispatcher.InvokeAsync(() =>
            {
                if (connected)
                {
                    SetCameraStatus(true, "통제실 연결됨");
                    AddLog(LogLevel.Info, "통제실 TCP 연결 성공");
                    CameraOverlay.Visibility = Visibility.Collapsed;
                }
                else
                {
                    SetCameraStatus(false, "연결 끊김");
                    // 비상 중 연결이 끊겨도 오버레이는 유지
                    if (!_emergencyActive)
                        ShowStandby();
                }
            });
        }

        // =================================================================
        // 프레임 표시
        // =================================================================

        private void ShowFrame(byte[] jpg)
        {
            BitmapImage bmp;
            try
            {
                bmp = new BitmapImage();
                using var ms = new MemoryStream(jpg);
                bmp.BeginInit();
                bmp.CacheOption = BitmapCacheOption.OnLoad;
                bmp.StreamSource = ms;
                bmp.EndInit();
                bmp.Freeze();
            }
            catch { return; }

            Dispatcher.InvokeAsync(() =>
            {
                VideoImage.Source = bmp;
                if (CameraOverlay.Visibility != Visibility.Collapsed)
                    CameraOverlay.Visibility = Visibility.Collapsed;

                _frameCount++;
                CameraBadge.Opacity = (_frameCount / 15 % 2 == 0) ? 1.0 : 0.4;
            });
        }

        // =================================================================
        // 카메라/감지기 상태
        // =================================================================

        private void SetCameraStatus(bool ok, string text)
        {
            CamDot.Fill = new SolidColorBrush(ok
                ? Color.FromRgb(0x2E, 0xCC, 0x71)
                : Color.FromRgb(0xE7, 0x4C, 0x3C));
            CamStatusText.Text = text;
        }

        private void SetLevel(string text, LogLevel level)
        {
            LevelText.Text = text;
            var (badge, dot) = level switch
            {
                LogLevel.Danger => ("#5A1A1A", "#E74C3C"),
                LogLevel.Warning => ("#5A4A0F", "#F1C40F"),
                _ => ("#1F4D2E", "#2ECC71"),
            };
            LevelBadge.Background = (Brush)new BrushConverter().ConvertFromString(badge)!;
            OverallBadge.Background = (Brush)new BrushConverter().ConvertFromString(badge)!;
            OverallDot.Fill = (Brush)new BrushConverter().ConvertFromString(dot)!;
            OverallText.Text = text;
        }

        // =================================================================
        // 비상 상태
        // =================================================================

        private void EnterEmergency(string timestamp)
        {
            _emergencyActive = true;

            // TCP는 상시 연결 중

            var ts = string.IsNullOrEmpty(timestamp)
                ? DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
                : timestamp;
            EmergencyTime.Text = $"감지 시각  {ts}";
            LastDetectionText.Text = ts;

            EmergencyOverlay.Visibility = Visibility.Visible;
            _flash.Begin(this, true);
            _beacon.Begin(this, true);
            SetLevel("비상", LogLevel.Danger);

            try { _siren?.Play(); } catch { }
        }

        private DispatcherTimer? _cooldownTimer;
        private int _cooldownRemaining = 0;

        /// <summary>
        /// 확인/해제 버튼: 비상 오버레이 닫고 30초 쿨다운 시작.
        /// 30초 내 경고 해제를 안 하면 다시 비상 화면 표시.
        /// </summary>
        private void AckEmergency()
        {
            if (!_emergencyActive) return;
            _flash.Stop(this);
            _beacon.Stop(this);
            EmergencyOverlay.Visibility = Visibility.Collapsed;
            try { _siren?.Stop(); } catch { }

            _emergencyActive = false;
            _armed = false;  // 쿨다운 중 재진입 방지
            // StopTcp는 여기서 하지 않음 — 쿨다운 중에도 카메라 화면 유지

            // 30초 쿨다운 타이머 시작
            _cooldownRemaining = 30;
            AddLog(LogLevel.Warning, "비상 확인 — 30초 내 경고 해제 필요");

            _cooldownTimer?.Stop();
            _cooldownTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            _cooldownTimer.Tick += (_, _) =>
            {
                _cooldownRemaining--;
                if (_cooldownRemaining <= 0)
                {
                    _cooldownTimer?.Stop();
                    _armed = true;
                    AddLog(LogLevel.Danger, "쿨다운 만료 → 비상 상황 재표시");
                    EnterEmergency(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
                }
            };
            _cooldownTimer.Start();
        }

        /// <summary>
        /// 경고 해제 버튼: 완전 정상화 + 쿨다운 취소 + 감지 재활성화.
        /// </summary>
        private void ClearEmergency()
        {
            // 비상 중이면 오버레이도 닫기
            if (_emergencyActive)
            {
                _flash.Stop(this);
                _beacon.Stop(this);
                EmergencyOverlay.Visibility = Visibility.Collapsed;
                try { _siren?.Stop(); } catch { }
                _emergencyActive = false;
            }

            // 쿨다운 타이머 취소
            _cooldownTimer?.Stop();
            _cooldownTimer = null;

            // 통제실에 해제 신호 전송 → 통제실 자동 리셋 + UDP 브로드캐스트 중단
            _fallClient.SendClearSignal();

            // TCP는 상시 유지 (영상 계속 표시)

            // 1초 쿨다운 — 통제실 브로드캐스트 스레드가 완전히 멈출 때까지 대기
            _armed = false;
            _fallClient.SetCooldown(1);

            ShowStandby();
            SetLevel("정상", LogLevel.Info);
            AddLog(LogLevel.Info, "경고 해제 — 통제실 자동 리셋 요청");

            var resumeTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            resumeTimer.Tick += (_, _) =>
            {
                resumeTimer.Stop();
                _armed = true;
                AddLog(LogLevel.Info, "감지 재활성화 완료");
            };
            resumeTimer.Start();
        }

        // =================================================================
        // 버튼 핸들러
        // =================================================================

        private void TestButton_Click(object sender, RoutedEventArgs e)
        {
            AddLog(LogLevel.Warning, "테스트: 강제 감지 트리거");
            if (!_emergencyActive)
                EnterEmergency(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
        }

        private void CallEmergencyButton_Click(object sender, RoutedEventArgs e)
        {
            AddLog(LogLevel.Danger, "수동 비상 호출");
            if (!_emergencyActive)
                EnterEmergency(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
        }

        private void ClearButton_Click(object sender, RoutedEventArgs e) => ClearEmergency();
        private void AckButton_Click(object sender, RoutedEventArgs e) => AckEmergency();

        private void RestartCameraButton_Click(object sender, RoutedEventArgs e)
        {
            AddLog(LogLevel.Info, "TCP 재연결 시도");
            if (_emergencyActive)
            {
                // TCP 상시 유지 중 — 재연결 불필요
            }
        }

        // 보안실에서는 카메라 콤보박스 사용 안 함 — 빈 핸들러만 유지
        private void CameraCombo_SelectionChanged(object sender, SelectionChangedEventArgs e) { }
        private async void RefreshCamerasButton_Click(object sender, RoutedEventArgs e) { }

        private void SaveLogButton_Click(object sender, RoutedEventArgs e)
        {
            if (Logs.Count == 0)
            {
                MessageBox.Show("저장할 로그가 없습니다.", "로그 저장",
                    MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            var dlg = new SaveFileDialog
            {
                FileName = $"lab_log_{DateTime.Now:yyyyMMdd_HHmmss}.txt",
                Filter = "텍스트 파일 (*.txt)|*.txt|모든 파일 (*.*)|*.*",
            };
            if (dlg.ShowDialog() != true) return;

            try
            {
                var lines = Logs.Reverse().Select(l => l.ToString());
                File.WriteAllLines(dlg.FileName, lines);
                AddLog(LogLevel.Info, $"로그 저장 완료 ({Logs.Count}건)");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"저장 실패: {ex.Message}", "오류",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // =================================================================
        // 이벤트 로그
        // =================================================================

        private void AddLog(LogLevel level, string message)
        {
            if (!Dispatcher.CheckAccess())
            {
                Dispatcher.InvokeAsync(() => AddLog(level, message));
                return;
            }

            Logs.Insert(0, new LogEntry(level, message));
            while (Logs.Count > 500) Logs.RemoveAt(Logs.Count - 1);
            LogCountText.Text = $"{Logs.Count}건";
        }

        // =================================================================
        // 사이렌
        // =================================================================

        private void TrySetupSiren()
        {
            try
            {
                var path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "siren.wav");
                if (File.Exists(path))
                {
                    _siren = new MediaPlayer();
                    _siren.Open(new Uri(path));
                    _siren.MediaEnded += (_, _) =>
                    {
                        _siren!.Position = TimeSpan.Zero;
                        _siren.Play();
                    };
                }
            }
            catch { _siren = null; }
        }
    }
}