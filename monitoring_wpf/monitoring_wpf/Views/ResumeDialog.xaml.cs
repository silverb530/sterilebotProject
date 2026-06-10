using System.Windows;

namespace monitoring_wpf.Views
{
    public partial class ResumeDialog : Window
    {
        // true = 계속, false = 종료
        public bool ContinueExperiment { get; private set; } = true;

        public ResumeDialog()
        {
            InitializeComponent();
        }

        private void Continue_Click(object sender, RoutedEventArgs e)
        {
            ContinueExperiment = true;
            Close();
        }

        private void Exit_Click(object sender, RoutedEventArgs e)
        {
            ContinueExperiment = false;
            Close();
        }
    }
}
