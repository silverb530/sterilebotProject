using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using monitoring_wpf.Services;

namespace monitoring_wpf.Views
{
    public class HistoryDialog : Window
    {
        private static readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(3) };
        private readonly DataGrid _grid;
        private readonly StackPanel _pagePanel;

        private List<UsageLog> _allLogs = new();
        private int _currentPage = 1;
        private const int PageSize = 8;  // 한 페이지 행 수

        public HistoryDialog()
        {
            Title = "실험 이력";
            Width = 780;
            Height = 560;
            WindowStartupLocation = WindowStartupLocation.CenterOwner;
            ResizeMode = ResizeMode.NoResize;
            Background = new SolidColorBrush(Color.FromRgb(0x0B, 0x19, 0x29));

            var root = new Grid();
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });           // 헤더
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) }); // 그리드
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });           // 페이징
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });           // 닫기

            // ── 헤더 ──
            var header = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(0x1E, 0x3A, 0x5F)),
                Padding = new Thickness(24, 14, 24, 14)
            };
            header.Child = new TextBlock
            {
                Text = "📋  로봇 사용 기록",
                FontSize = 16,
                FontWeight = FontWeights.SemiBold,
                Foreground = Brushes.White,
                FontFamily = new FontFamily("Segoe UI")
            };
            Grid.SetRow(header, 0);
            root.Children.Add(header);

            // ── DataGrid ──
            var gridBorder = new Border
            {
                Margin = new Thickness(20, 16, 20, 0),
                Background = Brushes.White,
                CornerRadius = new CornerRadius(8)
            };
            _grid = new DataGrid
            {
                AutoGenerateColumns = false,
                IsReadOnly = true,
                CanUserResizeRows = false,
                HeadersVisibility = DataGridHeadersVisibility.Column,
                GridLinesVisibility = DataGridGridLinesVisibility.Horizontal,
                HorizontalGridLinesBrush = new SolidColorBrush(Color.FromRgb(0xF1, 0xF5, 0xF9)),
                RowBackground = Brushes.White,
                AlternatingRowBackground = new SolidColorBrush(Color.FromRgb(0xF8, 0xFA, 0xFC)),
                BorderThickness = new Thickness(0),
                FontFamily = new FontFamily("Segoe UI"),
                FontSize = 13,
                Foreground = new SolidColorBrush(Color.FromRgb(0x37, 0x41, 0x51))
            };
            _grid.Columns.Add(new DataGridTextColumn { Header = "날짜", Binding = new System.Windows.Data.Binding("Date"), Width = new DataGridLength(130) });
            _grid.Columns.Add(new DataGridTextColumn { Header = "연구원", Binding = new System.Windows.Data.Binding("Researcher"), Width = new DataGridLength(100), FontWeight = FontWeights.SemiBold });
            _grid.Columns.Add(new DataGridTextColumn { Header = "시작", Binding = new System.Windows.Data.Binding("Start"), Width = new DataGridLength(80) });
            _grid.Columns.Add(new DataGridTextColumn { Header = "종료", Binding = new System.Windows.Data.Binding("End"), Width = new DataGridLength(80) });
            _grid.Columns.Add(new DataGridTextColumn { Header = "소요", Binding = new System.Windows.Data.Binding("Duration"), Width = new DataGridLength(80) });

            // 상태 컬럼
            var statusTpl = new DataTemplate();
            var bdr = new FrameworkElementFactory(typeof(Border));
            bdr.SetValue(Border.CornerRadiusProperty, new CornerRadius(10));
            bdr.SetValue(Border.PaddingProperty, new Thickness(10, 3, 10, 3));
            bdr.SetValue(Border.BackgroundProperty, new SolidColorBrush(Color.FromRgb(0xD1, 0xFA, 0xE5)));
            bdr.SetValue(FrameworkElement.HorizontalAlignmentProperty, HorizontalAlignment.Left);
            var txt = new FrameworkElementFactory(typeof(TextBlock));
            txt.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding("Status"));
            txt.SetValue(TextBlock.FontSizeProperty, 12.0);
            txt.SetValue(TextBlock.ForegroundProperty, new SolidColorBrush(Color.FromRgb(0x06, 0x5F, 0x46)));
            bdr.AppendChild(txt);
            statusTpl.VisualTree = bdr;
            _grid.Columns.Add(new DataGridTemplateColumn { Header = "상태", CellTemplate = statusTpl, Width = new DataGridLength(100) });

            gridBorder.Child = _grid;
            Grid.SetRow(gridBorder, 1);
            root.Children.Add(gridBorder);

            // ── 페이지 버튼 영역 ──
            _pagePanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Center,
                Margin = new Thickness(0, 12, 0, 4)
            };
            Grid.SetRow(_pagePanel, 2);
            root.Children.Add(_pagePanel);

            // ── 닫기 버튼 ──
            var footer = new Border { Padding = new Thickness(20, 6, 20, 14) };
            var closeBtn = new Button
            {
                Content = "닫기",
                Width = 90,
                Height = 36,
                HorizontalAlignment = HorizontalAlignment.Right,
                Background = new SolidColorBrush(Color.FromRgb(0x37, 0x8A, 0xDD)),
                Foreground = Brushes.White,
                FontWeight = FontWeights.SemiBold,
                FontSize = 13,
                BorderThickness = new Thickness(0)
            };
            closeBtn.Click += (_, _) => Close();
            footer.Child = closeBtn;
            Grid.SetRow(footer, 3);
            root.Children.Add(footer);

            Content = root;
            Loaded += async (_, _) => await LoadDataAsync();
        }

        private async System.Threading.Tasks.Task LoadDataAsync()
        {
            try
            {
                var json = await _http.GetStringAsync("http://localhost:5000/api/usage");
                var logs = JsonSerializer.Deserialize<List<UsageLog>>(json);
                if (logs == null) return;
                _allLogs = logs;
                Dispatcher.Invoke(() =>
                {
                    BuildPageButtons();
                    ShowPage(1);
                });
            }
            catch { }
        }

        private int TotalPages => (int)Math.Ceiling(_allLogs.Count / (double)PageSize);

        private void BuildPageButtons()
        {
            _pagePanel.Children.Clear();
            for (int p = 1; p <= TotalPages; p++)
            {
                int page = p;  // 클로저 캡처
                var btn = new Button
                {
                    Content = p.ToString(),
                    Width = 36,
                    Height = 36,
                    Margin = new Thickness(4, 0, 4, 0),
                    FontSize = 13,
                    FontWeight = FontWeights.SemiBold,
                    BorderThickness = new Thickness(1),
                    Cursor = System.Windows.Input.Cursors.Hand
                };
                btn.Tag = page;
                btn.Click += (_, _) => ShowPage(page);
                _pagePanel.Children.Add(btn);
            }
        }

        private void ShowPage(int page)
        {
            _currentPage = page;

            // 현재 페이지 데이터
            var items = _allLogs
                .Skip((page - 1) * PageSize)
                .Take(PageSize)
                .ToList();
            _grid.ItemsSource = items;

            // 버튼 스타일 — 현재 페이지 강조
            foreach (Button btn in _pagePanel.Children)
            {
                bool isCurrent = (int)btn.Tag == page;
                btn.Background = isCurrent
                    ? new SolidColorBrush(Color.FromRgb(0x37, 0x8A, 0xDD))
                    : new SolidColorBrush(Color.FromRgb(0x1E, 0x3A, 0x5F));
                btn.Foreground = Brushes.White;
                btn.BorderBrush = isCurrent
                    ? new SolidColorBrush(Color.FromRgb(0x37, 0x8A, 0xDD))
                    : new SolidColorBrush(Color.FromRgb(0x3B, 0x82, 0xF6));
            }
        }
    }
}