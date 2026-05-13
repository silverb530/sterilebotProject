using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using monitoring_wpf.Services;

namespace monitoring_wpf.Views
{
    public partial class GripperView : UserControl
    {
        public GripperView() { InitializeComponent(); }

        public void UpdateState(FlaskState state)
        {
            RX.Text = ((int)state.Robot.X).ToString();
            RY.Text = ((int)state.Robot.Y).ToString();
            RZ.Text = ((int)state.Robot.Z).ToString();
            RRX.Text = ((int)state.Robot.Rx).ToString();
            RRY.Text = ((int)state.Robot.Ry).ToString();
            RRZ.Text = ((int)state.Robot.Rz).ToString();

            GripState.Text = state.Gripper == "open" ? "열림" : "닫힘 (집기 중)";
            GripState.Foreground = (SolidColorBrush)Application.Current.FindResource(
                state.Gripper == "open" ? "TealBrush" : "AmberBrush");
        }

        private void Log(string msg)
        {
            if (Window.GetWindow(this) is MainWindow mw) mw.AddLog("info", msg);
        }

        private void EstopBtn_Click(object s, RoutedEventArgs e) { if (Window.GetWindow(this) is MainWindow mw) mw.AddLog("err", "긴급정지"); }
        private void HomeBtn_Click(object s, RoutedEventArgs e) { Log("홈 복귀"); }
        private void ResetBtn_Click(object s, RoutedEventArgs e) { Log("상태 초기화"); }
        private void ReconnectBtn_Click(object s, RoutedEventArgs e) { Log("재연결"); }
        private void FsmResetBtn_Click(object s, RoutedEventArgs e) { Log("FSM 리셋"); }
        private void GripOpen_Click(object s, RoutedEventArgs e) { Log("그리퍼 열기"); }
        private void GripClose_Click(object s, RoutedEventArgs e) { Log("그리퍼 닫기"); }
        private void GazeToggle_Click(object s, RoutedEventArgs e) { Log("시선 제어 토글"); }
    }
}
