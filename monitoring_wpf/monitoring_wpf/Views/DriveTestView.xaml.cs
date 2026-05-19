using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

namespace monitoring_wpf.Views
{
    public partial class DriveTestView : UserControl
    {
        /// <summary>테스트 완료 후 메인 화면으로 이동할 콜백</summary>
        public Action? OnBack { get; set; }

        private DispatcherTimer? _progressTimer;
        private double _progress = 0;

        // ── 설정 ──────────────────────────────
        // 총 소요 시간: 5초  (interval 50ms × 100 ticks)
        private const double TickInterval = 50;   // ms
        private const double IncPerTick   = 1.0;  // % 증가량 (100 / (5000/50) = 1.0)
        // ─────────────────────────────────────

        public DriveTestView()
        {
            InitializeComponent();

            // 화면이 표시될 때마다 처음부터 시작
            IsVisibleChanged += (_, e) =>
            {
                if ((bool)e.NewValue)
                    StartProgress();
                else
                    StopProgress();
            };
        }

        private void StartProgress()
        {
            // 초기화
            _progress = 0;
            ProgressFill.Width = 0;
            ProgressPct.Text   = "0 %";
            StatusTitle.Text   = "구동 테스트 중입니다";
            StatusSub.Text     = "잠시만 기다려 주세요...";
            SpinnerArc.Visibility  = Visibility.Visible;
            CheckBadge.Visibility  = Visibility.Collapsed;

            // 진행 타이머 시작
            _progressTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(TickInterval)
            };
            _progressTimer.Tick += ProgressTick;
            _progressTimer.Start();
        }

        private void StopProgress()
        {
            _progressTimer?.Stop();
            _progressTimer = null;
        }

        private void ProgressTick(object? sender, EventArgs e)
        {
            _progress += IncPerTick;

            // 진행 바 너비 갱신 (부모 ActualWidth 기준)
            double trackW = ProgressTrack.ActualWidth;
            if (trackW > 0)
                ProgressFill.Width = Math.Min(trackW, _progress / 100.0 * trackW);

            ProgressPct.Text = $"{(int)Math.Min(100, _progress)} %";

            if (_progress < 100) return;

            // ── 100% 완료 ──
            _progressTimer?.Stop();
            _progressTimer = null;

            ProgressFill.Width       = ProgressTrack.ActualWidth;
            ProgressFill.Background  = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A)); // 초록
            ProgressPct.Text         = "100 %";
            StatusTitle.Text         = "구동 테스트 완료!";
            StatusSub.Text           = "메인 화면으로 이동합니다...";
            SpinnerArc.Visibility    = Visibility.Collapsed;
            CheckBadge.Visibility    = Visibility.Visible;

            // 0.8초 후 자동 이동
            var delay = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(800) };
            delay.Tick += (_, _) =>
            {
                delay.Stop();
                OnBack?.Invoke();
            };
            delay.Start();
        }
    }
}
