using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using monitoring_wpf.Services;

namespace monitoring_wpf
{
    public partial class MainWindow : Window
    {
        private readonly FlaskClient _flask = new("http://localhost:5000");
        private readonly DispatcherTimer _clock = new();
        private readonly List<LogItem> _allLogs = new();
        private string _logFilter = "all";

        public MainWindow()
        {
            InitializeComponent();
            SetupClock();
            SetupFlask();
            SetActiveTab("gaze");
            AddLog("ok", "SterileBot Monitor 시작");
            AddLog("info", "Flask 연결 중...");
        }

        private void SetupClock()
        {
            _clock.Interval = TimeSpan.FromSeconds(1);
            _clock.Tick += (_, _) => ClockText.Text = DateTime.Now.ToString("HH:mm:ss");
            _clock.Start();
        }

        private void SetupFlask()
        {
            _flask.Connected += () => Dispatcher.Invoke(() =>
            {
                ConnDot.Fill = (SolidColorBrush)FindResource("TealBrush");
                ConnLabel.Text = "FLASK 연결됨";
                ConnLabel.Foreground = (SolidColorBrush)FindResource("TealBrush");
                AddLog("ok", "Flask 연결됨");
            });

            _flask.ConnectionError += _ => Dispatcher.Invoke(() =>
            {
                ConnDot.Fill = (SolidColorBrush)FindResource("RedBrush");
                ConnLabel.Text = "FLASK 연결 안됨";
                ConnLabel.Foreground = (SolidColorBrush)FindResource("RedBrush");
            });

            _flask.StateUpdated += state => Dispatcher.Invoke(() =>
            {
                // 기존 코드
                ApplyFsm(state.Fsm);
                GazeView.UpdateState(state);
                GripperView.UpdateState(state);

                Dispatcher.BeginInvoke(new Action(() =>
                {
                    ConnDot.Fill = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D4AA"));
                    ConnLabel.Text = "FLASK 연결됨";
                    ConnLabel.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D4AA"));
                }));
            });

            _flask.StartPolling(500);
        }

        private void ApplyFsm(string fsm)
        {
            var (bg, border, fg, lbl) = fsm switch
            {
                "MOVING" => ("BlueDimBrush", "BlueBrush", "BlueBrush", "MOVING"),
                "GRIP" => ("AmberDimBrush", "AmberBrush", "AmberBrush", "GRIP"),
                "ESTOP" => ("RedDimBrush", "RedBrush", "RedBrush", "E-STOP"),
                _ => ("TealDimBrush", "TealBrush", "TealBrush", "IDLE"),
            };
            FsmBadge.Background = (SolidColorBrush)FindResource(bg);
            FsmBadge.BorderBrush = (SolidColorBrush)FindResource(border);
            FsmDot.Fill = (SolidColorBrush)FindResource(fg);
            FsmText.Foreground = (SolidColorBrush)FindResource(fg);
            FsmText.Text = lbl;
        }

        private void Tab_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn) SetActiveTab(btn.Tag?.ToString() ?? "gaze");
        }

        private void SetActiveTab(string tab)
        {
            GazeView.Visibility = tab == "gaze" ? Visibility.Visible : Visibility.Collapsed;
            GripperView.Visibility = tab == "gripper" ? Visibility.Visible : Visibility.Collapsed;
            OverviewView.Visibility = tab == "overview" ? Visibility.Visible : Visibility.Collapsed;

            TabGaze.Foreground = (SolidColorBrush)FindResource(tab == "gaze" ? "TealBrush" : "TextDimBrush");
            TabGripper.Foreground = (SolidColorBrush)FindResource(tab == "gripper" ? "TealBrush" : "TextDimBrush");
            TabOverview.Foreground = (SolidColorBrush)FindResource(tab == "overview" ? "TealBrush" : "TextDimBrush");
        }

        public void AddLog(string type, string msg)
        {
            _allLogs.Add(new LogItem(type, msg));
            RefreshLogList();
            LogScroll.ScrollToEnd();
        }

        private void RefreshLogList()
        {
            LogList.ItemsSource = _logFilter == "all"
                ? _allLogs.ToList()
                : _allLogs.Where(l => l.Type == _logFilter).ToList();
        }

        private void LogFilter_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn) { _logFilter = btn.Tag?.ToString() ?? "all"; RefreshLogList(); }
        }

        private void ClearLog_Click(object sender, RoutedEventArgs e)
        {
            _allLogs.Clear(); RefreshLogList();
        }

        protected override void OnClosed(EventArgs e)
        {
            _flask.StopPolling(); _flask.Dispose(); _clock.Stop();
            base.OnClosed(e);
        }
    }

    public class LogItem
    {
        public string Type { get; }
        public string Ts { get; }
        public string Msg { get; }
        public string TagText { get; }
        public SolidColorBrush TagFg { get; }
        public SolidColorBrush TagBg { get; }

        public LogItem(string type, string msg)
        {
            Type = type; Msg = msg;
            Ts = DateTime.Now.ToString("HH:mm:ss");
            TagText = type.ToUpper();
            (TagFg, TagBg) = type switch
            {
                "ok" => (B("#00D4AA"), B("#1600D4AA")),
                "warn" => (B("#F5A623"), B("#20F5A623")),
                "err" => (B("#FF4455"), B("#20FF4455")),
                _ => (B("#4A9EFF"), B("#164A9EFF")),
            };
        }

        private static SolidColorBrush B(string hex) =>
            new((Color)ColorConverter.ConvertFromString(hex));
    }
}
