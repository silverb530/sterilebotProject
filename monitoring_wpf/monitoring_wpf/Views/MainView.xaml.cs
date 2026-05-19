using System;
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
        public Action? OnStart     { get; set; }
        public Action? OnExit      { get; set; }

        private readonly DispatcherTimer _clock = new();

        private const int LabCamIndex = 0;
        private const int ArmCamIndex = 1;

        public MainView()
        {
            InitializeComponent();

            _clock.Interval = TimeSpan.FromSeconds(1);
            _clock.Tick += (_, _) => ClockText.Text = DateTime.Now.ToString("HH:mm:ss");
            _clock.Start();

            IsVisibleChanged += (_, _) =>
            {
                if (IsVisible)
                {
                    // ★ 인증된 연구원 이름 표시
                    if (!string.IsNullOrEmpty(MainWindow.AuthName))
                        UserLabel.Text = $"{MainWindow.AuthName} {MainWindow.AuthRole}";

                    LabCam.Start(cameraIndex: LabCamIndex, noSignalLabel: "조감 카메라 대기 중");
                    ArmCam.Start(cameraIndex: ArmCamIndex, noSignalLabel: "로봇암 카메라 대기 중");
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
            var hex   = ok ? "#22C55E" : "#EF4444";
            var label = ok ? "서버 연결됨" : "서버 연결 안됨";
            var c = (Color)ColorConverter.ConvertFromString(hex);
            ConnDot.Fill         = new SolidColorBrush(c);
            ConnLabel.Foreground = new SolidColorBrush(c);
            ConnLabel.Text       = label;
        }

        public void UpdateState(FlaskState state)
        {
            SetConnected(true);

            // 인증된 이름 우선 표시, 없으면 Flask state 사용
            if (string.IsNullOrEmpty(MainWindow.AuthName))
                UserLabel.Text = state.User;

            StatusLabel.Text =
                $"가스농도  {state.Gas:F0} ppm    " +
                $"온도  {state.Temp:F1} °C    " +
                $"습도  {state.Humidity:F0} %    " +
                $"│    상태:  {state.StatusText}";
        }

        private void DriveTest_Click(object s, RoutedEventArgs e) => OnDriveTest?.Invoke();
        private void Start_Click(object s, RoutedEventArgs e)     => OnStart?.Invoke();
        private void Exit_Click(object s, RoutedEventArgs e)      => OnExit?.Invoke();
    }
}
