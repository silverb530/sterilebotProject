using System;
using System.Windows;
using System.Windows.Media;
using System.Windows.Threading;
using monitoring_wpf.service;

namespace monitoring_wpf.Views
{
    public partial class VentingWindow : Window
    {
        private readonly DispatcherTimer _timer = new();
        private int _remaining = 180;   // 3분 카운트다운 (초)

        public VentingWindow()
        {
            InitializeComponent();

            _timer.Interval = TimeSpan.FromSeconds(1);
            _timer.Tick += (_, _) =>
            {
                _remaining--;
                if (_remaining > 0)
                    RemainText.Text = $"{_remaining / 60:D2}:{_remaining % 60:D2}";  // "남은 시간:" 빼고 숫자만
                else
                    RemainText.Text = "00:00";
            };
            _timer.Start();

            Closed += (_, _) => _timer.Stop();
        }

        // Pi에서 받은 현재 가스 농도 표시
        public void UpdateGas(int gas)
        {
            GasText.Text = gas.ToString();   // 숫자만 ("현재 가스 농도:", "ppm"은 XAML 라벨로 분리)
            GasText.Foreground = new SolidColorBrush(
                gas < 260 ? Color.FromRgb(0x4A, 0xDE, 0x80)
                          : Color.FromRgb(0xFB, 0x92, 0x3C));
        }

        private void ForceExit_Click(object sender, RoutedEventArgs e)
        {
            _ = EmergencyListenerService.SendToPiAsync("VENT_STOP");
            Close();
        }
    }
}