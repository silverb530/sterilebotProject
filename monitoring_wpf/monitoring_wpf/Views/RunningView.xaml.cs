using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using monitoring_wpf.Services;

namespace monitoring_wpf.Views
{
    public partial class RunningView : UserControl
    {
        public Action? OnEmergencyStop { get; set; }
        public Action? OnResume        { get; set; }
        public Action? OnExit          { get; set; }

        private bool _isEmergency = false;
        private bool _isPaused    = false;
        private readonly DispatcherTimer _clock = new();

        private const int LabCamIndex = 0;
        private const int ArmCamIndex = 1;

        private bool _labIsMain = true;

        public RunningView()
        {
            InitializeComponent();

            _clock.Interval = TimeSpan.FromSeconds(1);
            _clock.Tick += (_, _) => ClockText.Text = DateTime.Now.ToString("HH:mm:ss");
            _clock.Start();

            IsVisibleChanged += (_, _) =>
            {
                if (IsVisible) StartCameras();
                else           StopCameras();
            };
        }

        private void StartCameras() => ApplyCameraLayout();

        private void StopCameras()
        {
            MainCam.Stop();
            PipCam.Stop();
        }

        private void ApplyCameraLayout()
        {
            int mainIdx    = _labIsMain ? LabCamIndex : ArmCamIndex;
            int pipIdx     = _labIsMain ? ArmCamIndex : LabCamIndex;
            string mainLbl = _labIsMain ? "실험실 조감캠" : "로봇암 카메라";
            string pipLbl  = _labIsMain ? "로봇암 카메라" : "실험실 조감캠";
            Color mainDot  = _labIsMain
                ? Color.FromRgb(0x4A, 0xDE, 0x80)
                : Color.FromRgb(0xFB, 0x92, 0x3C);
            Color pipDot   = _labIsMain
                ? Color.FromRgb(0xFB, 0x92, 0x3C)
                : Color.FromRgb(0x4A, 0xDE, 0x80);

            MainCam.Stop();
            PipCam.Stop();
            MainCam.Start(mainIdx, mainLbl + " 대기 중");
            PipCam.Start(pipIdx,  pipLbl  + " 대기 중");

            MainLabelText.Text = mainLbl;
            PipLabelText.Text  = pipLbl;
            MainDot.Fill       = new SolidColorBrush(mainDot);
            PipDot.Fill        = new SolidColorBrush(pipDot);
        }

        private void SwapCameras()
        {
            _labIsMain = !_labIsMain;
            ApplyCameraLayout();
        }

        // ── 클릭 핸들러 ──────────────────────────────
        // 큰 화면(MainCam)은 클릭해도 아무 동작 없음
        private void MainCam_Click(object s, System.Windows.Input.MouseButtonEventArgs e)
        {
            // 아무것도 하지 않음 — 큰 화면 클릭 비활성화
        }

        // 작은 PIP 화면만 클릭 시 전환
        private void PipCam_Click(object s, System.Windows.Input.MouseButtonEventArgs e)
            => SwapCameras();

        // ══════════════════════════════════════════
        // 비상 / 정상 전환
        // ══════════════════════════════════════════
        public void SetEmergency(bool emergency)
        {
            _isEmergency = emergency;

            if (emergency)
            {
                ScenePanel.Visibility     = Visibility.Collapsed;
                EmergencyPanel.Visibility = Visibility.Visible;

                BadgeBg.Color       = Color.FromRgb(0x7F, 0x1D, 0x1D);
                BadgeDotColor.Color = Color.FromRgb(0xEF, 0x44, 0x44);
                BadgeFg.Color       = Color.FromRgb(0xEF, 0x44, 0x44);
                BadgeText.Text      = "비상상황 — 중지";

                EstopBorder.Background  = new SolidColorBrush(Color.FromRgb(0x7F, 0x1D, 0x1D));
                EstopBorder.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFE, 0xCA, 0xCA));
                EstopIcon.Foreground    = new SolidColorBrush(Colors.White);
                EstopIcon.Text          = "✓";
                EstopLabel.Foreground   = new SolidColorBrush(Colors.White);
                EstopLabel.Text         = "정지 해제";

                StatusChip.Background  = new SolidColorBrush(Color.FromRgb(0xFE, 0xF2, 0xF2));
                StatusChip.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFC, 0xA5, 0xA5));
                SafetyDot.Fill         = new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26));
                StatusLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x7F, 0x1D, 0x1D));
                StatusLabel.Text       = "비상상황";
            }
            else
            {
                ScenePanel.Visibility     = Visibility.Visible;
                EmergencyPanel.Visibility = Visibility.Collapsed;

                BadgeBg.Color       = Color.FromRgb(0x15, 0x80, 0x3D);
                BadgeDotColor.Color = Color.FromRgb(0x4A, 0xDE, 0x80);
                BadgeFg.Color       = Color.FromRgb(0x4A, 0xDE, 0x80);
                BadgeText.Text      = "실행중";

                EstopBorder.Background  = new SolidColorBrush(Color.FromRgb(0xFE, 0xF2, 0xF2));
                EstopBorder.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFC, 0xA5, 0xA5));
                EstopIcon.Foreground    = new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26));
                EstopIcon.Text          = "⚠";
                EstopLabel.Foreground   = new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26));
                EstopLabel.Text         = "비상 정지";

                StatusChip.Background  = new SolidColorBrush(Color.FromRgb(0xDC, 0xFC, 0xE7));
                StatusChip.BorderBrush = new SolidColorBrush(Color.FromRgb(0x86, 0xEF, 0xAC));
                SafetyDot.Fill         = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A));
                StatusLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x15, 0x80, 0x3D));
                StatusLabel.Text       = "안전";
            }
        }

        // ══════════════════════════════════════════
        // Flask 상태 수신
        // ══════════════════════════════════════════
        public void UpdateState(FlaskState state)
        {
            GasVal.Text  = $"{state.Gas:F0}";
            TempVal.Text = $"{state.Temp:F1}";
            HumVal.Text  = $"{state.Humidity:F0}";

            GasVal.Foreground = state.Gas > 80
                ? new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26))
                : state.Gas > 50
                    ? new SolidColorBrush(Color.FromRgb(0xD9, 0x77, 0x06))
                    : new SolidColorBrush(Color.FromRgb(0x1E, 0x29, 0x3B));

            if (_isEmergency) return;

            bool warn = state.StatusText.Contains("경고") || state.StatusText.Contains("위험");
            StatusLabel.Text       = warn ? "경고" : "안전";
            SafetyDot.Fill         = new SolidColorBrush(warn
                ? Color.FromRgb(0xD9, 0x77, 0x06)
                : Color.FromRgb(0x16, 0xA3, 0x4A));
            StatusLabel.Foreground = new SolidColorBrush(warn
                ? Color.FromRgb(0x92, 0x40, 0x0E)
                : Color.FromRgb(0x15, 0x80, 0x3D));
            StatusChip.Background  = new SolidColorBrush(warn
                ? Color.FromRgb(0xFF, 0xF7, 0xED)
                : Color.FromRgb(0xDC, 0xFC, 0xE7));
            StatusChip.BorderBrush = new SolidColorBrush(warn
                ? Color.FromRgb(0xFD, 0xBA, 0x74)
                : Color.FromRgb(0x86, 0xEF, 0xAC));
        }

        // ══════════════════════════════════════════
        // 버튼 핸들러
        // ══════════════════════════════════════════
        private void EmergencyStop_Click(object s, System.Windows.Input.MouseButtonEventArgs e)
        {
            if (_isEmergency) OnResume?.Invoke();
            else              OnEmergencyStop?.Invoke();
        }

        private void PauseResume_Click(object s, RoutedEventArgs e)
        {
            _isPaused = !_isPaused;
            PauseResumeBtn.Content = _isPaused ? "▶  재  개" : "⏸  일시 정지";
        }

        private void ResetState_Click(object s, RoutedEventArgs e) => OnResume?.Invoke();

        private void Exit_Click(object s, RoutedEventArgs e) => OnExit?.Invoke();

        private void Reset_Click(object s, RoutedEventArgs e)
        {
            // 리셋: 비상 해제 + 맵 초기화
            SetEmergency(false);
            ClearMapHighlight();
        }

        // ══════════════════════════════════════════
        // 맵 시험관 하이라이트
        // ══════════════════════════════════════════
        private Ellipse? _lastHighlighted;

        public void HighlightSlot(string slotName)
        {
            ClearMapHighlight();

            var slot = this.FindName($"Slot{slotName}") as Ellipse;
            if (slot != null)
            {
                slot.Fill   = new SolidColorBrush(Color.FromRgb(0x22, 0xC5, 0x5E)); // 초록
                slot.Stroke = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A));
                slot.StrokeThickness = 3;
                _lastHighlighted = slot;
                MapStatusText.Text = $"▶ {slotName} 선택됨";
            }
        }

        public void ClearMapHighlight()
        {
            if (_lastHighlighted != null)
            {
                _lastHighlighted.Fill   = new SolidColorBrush(Color.FromRgb(0x3B, 0x82, 0xF6)); // 원래 파란색
                _lastHighlighted.Stroke = new SolidColorBrush(Color.FromRgb(0x25, 0x63, 0xEB));
                _lastHighlighted.StrokeThickness = 1.5;
                _lastHighlighted = null;
            }
            MapStatusText.Text = "";
        }
    }
}
