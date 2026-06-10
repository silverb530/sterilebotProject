using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace monitoring_wpf.Views
{
    /// <summary>
    /// 실행 시작 전 사용자 이름 + 로봇 연결 여부를 묻는 팝업.
    /// 코드로만 UI 구성 (XAML 없이) — 별도 파일 추가 부담 최소화.
    /// </summary>
    public class StartupDialog : Window
    {
        public string UserName { get; private set; } = "default";
        public bool UseRobot { get; private set; } = false;
        //public string RobotIp { get; private set; } = "192.168.0.27";
        public string RobotIp { get; private set; } = "192.168.0.32";
        public int RobotPort { get; private set; } = 5001;

        private readonly TextBox _nameBox;
        private readonly CheckBox _robotCheck;
        private readonly TextBox _ipBox;
        private readonly TextBox _portBox;

        public StartupDialog(string defaultName = "")
        {
            Title = "실험 시작 설정";
            Width = 380;
            Height = 420;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            ResizeMode = ResizeMode.NoResize;
            SizeToContent = SizeToContent.Height;
            MinHeight = 380;
            Background = new SolidColorBrush(Color.FromRgb(0x1E, 0x29, 0x3B));

            var root = new StackPanel { Margin = new Thickness(24) };

            // 제목
            root.Children.Add(new TextBlock
            {
                Text = "실험 시작",
                FontSize = 20,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Margin = new Thickness(0, 0, 0, 4)
            });
            root.Children.Add(new TextBlock
            {
                Text = "트래킹 / 제스처 프로그램을 실행합니다",
                FontSize = 12,
                Foreground = new SolidColorBrush(Color.FromRgb(0x94, 0xA3, 0xB8)),
                Margin = new Thickness(0, 0, 0, 18)
            });

            // 사용자 이름
            root.Children.Add(Label("사용자 이름 (캘리브레이션 파일명)"));
            _nameBox = new TextBox
            {
                Text = string.IsNullOrWhiteSpace(defaultName) ? "" : defaultName,
                Padding = new Thickness(6),
                FontSize = 14,
                Margin = new Thickness(0, 0, 0, 16)
            };
            root.Children.Add(_nameBox);

            // 로봇 연결 체크박스
            _robotCheck = new CheckBox
            {
                Content = "로봇 연결 (체크 해제 시 시뮬레이션)",
                Foreground = Brushes.White,
                FontSize = 14,
                Margin = new Thickness(0, 0, 0, 10)
            };
            _robotCheck.Checked += (_, _) => ToggleRobotFields(true);
            _robotCheck.Unchecked += (_, _) => ToggleRobotFields(false);
            root.Children.Add(_robotCheck);

            // 로봇 IP / 포트 (체크 시에만 활성)
            var ipPanel = new StackPanel { Orientation = Orientation.Horizontal };
            _ipBox = new TextBox
            {
                //Text = "192.168.0.27",
                Text = "192.168.0.32",
                Width = 160,
                Padding = new Thickness(6),
                IsEnabled = false,
                Margin = new Thickness(0, 0, 8, 0)
            };
            _portBox = new TextBox
            {
                Text = "5001",
                Width = 70,
                Padding = new Thickness(6),
                IsEnabled = false
            };
            ipPanel.Children.Add(_ipBox);
            ipPanel.Children.Add(_portBox);
            root.Children.Add(ipPanel);

            // 버튼
            var btnPanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin = new Thickness(0, 22, 0, 0)
            };
            var cancelBtn = new Button
            {
                Content = "취소",
                Width = 80,
                Height = 34,
                Margin = new Thickness(0, 0, 8, 0)
            };
            cancelBtn.Click += (_, _) => { DialogResult = false; Close(); };
            var okBtn = new Button
            {
                Content = "시작",
                Width = 80,
                Height = 34,
                Background = new SolidColorBrush(Color.FromRgb(0x37, 0x8A, 0xDD)),
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold
            };
            okBtn.Click += OkClick;
            btnPanel.Children.Add(cancelBtn);
            btnPanel.Children.Add(okBtn);
            root.Children.Add(btnPanel);

            Content = root;
        }

        private TextBlock Label(string text) => new TextBlock
        {
            Text = text,
            FontSize = 12,
            Foreground = new SolidColorBrush(Color.FromRgb(0x94, 0xA3, 0xB8)),
            Margin = new Thickness(0, 0, 0, 4)
        };

        private void ToggleRobotFields(bool on)
        {
            _ipBox.IsEnabled = on;
            _portBox.IsEnabled = on;
        }

        private void OkClick(object sender, RoutedEventArgs e)
        {
            string name = _nameBox.Text.Trim();
            if (string.IsNullOrWhiteSpace(name))
            {
                MessageBox.Show("사용자 이름을 입력하세요.", "확인",
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            UserName = name;
            UseRobot = _robotCheck.IsChecked == true;
            RobotIp = _ipBox.Text.Trim();
            if (!int.TryParse(_portBox.Text.Trim(), out int p)) p = 5001;
            RobotPort = p;

            DialogResult = true;
            Close();
        }
    }
}