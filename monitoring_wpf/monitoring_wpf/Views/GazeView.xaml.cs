using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using monitoring_wpf.Services;

namespace monitoring_wpf.Views
{
    public partial class GazeView : UserControl
    {
        public GazeView() { InitializeComponent(); }

        private void GazeCanvas_SizeChanged(object s, SizeChangedEventArgs e)
        {
            UpdateGazeCanvas(640, 400);
        }

        public void UpdateState(FlaskState state)
        {
            bool blink = state.Ear < 0.20;

            EarVal.Text = state.Ear.ToString("F2");
            EarVal.Foreground = (SolidColorBrush)Application.Current.FindResource(blink ? "RedBrush" : "TealBrush");
            EarStatus.Text = blink ? "⚠ 깜빡임 감지 — 그리퍼 닫기" : "정상 — 깜빡임 없음";

            double trackW = (EarFill.Parent as FrameworkElement)?.ActualWidth ?? 0;
            if (trackW > 0) EarFill.Width = Math.Max(0, state.Ear / 0.5 * trackW);
            EarFill.Background = (SolidColorBrush)Application.Current.FindResource(blink ? "RedBrush" : "TealBrush");

            DwellVal.Text = Math.Round(state.Dwell).ToString();
            double dwTrackW = (DwellFill.Parent as FrameworkElement)?.ActualWidth ?? 0;
            if (dwTrackW > 0) DwellFill.Width = Math.Max(0, state.Dwell / 100.0 * dwTrackW);
            DwellStatus.Text = state.Dwell > 0 ? $"응시 중... {(state.Dwell / 100.0 * 1.5):F1}s" : "대기 중";

            GCx.Text = state.Gaze.Cx.ToString();
            GCy.Text = state.Gaze.Cy.ToString();
            GRx.Text = state.Gaze.Rx.ToString();
            GRy.Text = state.Gaze.Ry.ToString();
            CamLabel0.Text = $"cx:{state.Gaze.Cx} cy:{state.Gaze.Cy}";

            UpdateGazeCanvas(state.Gaze.Cx, state.Gaze.Cy);
        }

        private void UpdateGazeCanvas(int cx, int cy)
        {
            double cw = GazeCanvas.ActualWidth;
            double ch = GazeCanvas.ActualHeight;
            if (cw <= 0 || ch <= 0) return;

            GazeLineH.X1 = 0; GazeLineH.X2 = cw; GazeLineH.Y1 = ch / 2; GazeLineH.Y2 = ch / 2;
            GazeLineV.X1 = cw / 2; GazeLineV.X2 = cw / 2; GazeLineV.Y1 = 0; GazeLineV.Y2 = ch;

            double px = (cx - 160.0) / (1120 - 160) * cw;
            double py = (cy - 80.0) / (720 - 80) * ch;

            Canvas.SetLeft(GazeDot, px - 5);
            Canvas.SetTop(GazeDot, py - 5);
            Canvas.SetLeft(GazeRing, px - 12);
            Canvas.SetTop(GazeRing, py - 12);
        }

        private void EstopBtn_Click(object s, RoutedEventArgs e)
        {
            if (Window.GetWindow(this) is MainWindow mw)
                mw.AddLog("err", "긴급정지");
        }
    }
}
