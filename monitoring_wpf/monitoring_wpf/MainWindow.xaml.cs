using System;
using System.Windows;
using monitoring_wpf.Services;

namespace monitoring_wpf
{
    public partial class MainWindow : Window
    {
        private readonly FlaskClient _flask = new("http://localhost:5000");

        // 인증된 연구원 정보
        public static string AuthName { get; set; } = "";
        public static string AuthRole { get; set; } = "";

        public MainWindow()
        {
            InitializeComponent();
            SetupFlask();

            // Wire navigation callbacks
            ViewFaceAuth.OnAuthComplete  = () => Navigate("main");
            ViewMain.OnDriveTest         = () => Navigate("drivetest");
            ViewMain.OnStart             = () => Navigate("running");
            ViewMain.OnExit              = () => Application.Current.Shutdown();
            ViewDriveTest.OnBack         = () => Navigate("main");
            ViewRunning.OnEmergencyStop  = () => ViewRunning.SetEmergency(true);
            ViewRunning.OnResume         = () => ViewRunning.SetEmergency(false);
            ViewRunning.OnExit           = () => Navigate("main");

            // 얼굴 인증 화면으로 시작
            Navigate("faceauth");
        }

        private void Navigate(string view)
        {
            ViewFaceAuth.Visibility  = view == "faceauth"  ? Visibility.Visible : Visibility.Collapsed;
            ViewMain.Visibility      = view == "main"      ? Visibility.Visible : Visibility.Collapsed;
            ViewDriveTest.Visibility = view == "drivetest" ? Visibility.Visible : Visibility.Collapsed;
            ViewRunning.Visibility   = view == "running"   ? Visibility.Visible : Visibility.Collapsed;

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
            _flask.StopPolling();
            _flask.Dispose();
            base.OnClosed(e);
        }
    }
}
