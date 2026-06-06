using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using monitoring_wpf.Services;

namespace monitoring_wpf.Views
{
    public partial class MainView : UserControl
    {
        public Action? OnDriveTest { get; set; }
        public Action? OnStart { get; set; }
        public Action? OnExit { get; set; }

        private readonly DispatcherTimer _clock = new();
        private const string GestureStreamUrl = "http://localhost:8091/stream";

        private static int LabCamIndex => LoadLabCamIndex();

        private static int LoadLabCamIndex()
        {
            try
            {
                var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
                while (dir != null)
                {
                    var path = Path.Combine(dir.FullName, "gesture_learning", "camera_indices.json");
                    if (File.Exists(path))
                    {
                        var json = File.ReadAllText(path);
                        var map = JsonSerializer.Deserialize<Dictionary<string, int>>(json);
                        if (map != null && map.TryGetValue("lab", out int idx))
                            return idx;
                        return 2; // 기본값
                    }
                    dir = dir.Parent;
                }
            }
            catch { }
            return 2; // 기본값
        }

        public MainView()
        {
            InitializeComponent();

            _clock.Interval = TimeSpan.FromSeconds(1);
            _clock.Tick += (_, _) => ClockText.Text = DateTime.Now.ToString("HH:mm:ss");
            _clock.Start();

            IsVisibleChanged += async (_, _) =>
            {
                if (IsVisible)
                {
                    if (!string.IsNullOrEmpty(MainWindow.AuthName))
                        UserLabel.Text = $"{MainWindow.AuthName} {MainWindow.AuthRole}";

                    // Zone_tracker 종료 후 카메라 해제까지 대기
                    await System.Threading.Tasks.Task.Delay(1500);

                    // 실험실 조감캠 — camera_indices.json 의 "lab" 키로 동적 탐색
                    LabCam.Start(cameraIndex: LabCamIndex, noSignalLabel: "조감 카메라 대기 중");
                    // ArmCam — 제스처 인식 MJPEG 스트림 (실험 시작 전엔 대기 중으로 표시)
                    ArmCam.StartMjpeg(GestureStreamUrl, "손동작 인식 대기 중");
                }
                else
                {
                    LabCam.Stop();
                    ArmCam.Stop();
                }
            };
        }

        public void SetConnected(bool ok)
        {
            var hex = ok ? "#22C55E" : "#EF4444";
            var label = ok ? "서버 연결됨" : "서버 연결 안됨";
            var c = (Color)ColorConverter.ConvertFromString(hex);
            ConnDot.Fill = new SolidColorBrush(c);
            ConnLabel.Foreground = new SolidColorBrush(c);
            ConnLabel.Text = label;
        }

        public void UpdateState(FlaskState state)
        {
            SetConnected(true);
            if (string.IsNullOrEmpty(MainWindow.AuthName))
                UserLabel.Text = state.User;

            StatusLabel.Text =
                $"가스농도  {state.Gas:F0} ppm    " +
                $"온도  {state.Temp:F1} °C    " +
                $"습도  {state.Humidity:F0} %    " +
                $"│    상태:  {state.StatusText}";
        }

        private void DriveTest_Click(object s, RoutedEventArgs e) => OnDriveTest?.Invoke();
        private void Start_Click(object s, RoutedEventArgs e) => OnStart?.Invoke();
        private void Exit_Click(object s, RoutedEventArgs e) => OnExit?.Invoke();

        private void History_Click(object s, RoutedEventArgs e)
        {
            var dlg = new HistoryDialog();
            dlg.Owner = System.Windows.Window.GetWindow(this);
            dlg.ShowDialog();
        }
    }
}