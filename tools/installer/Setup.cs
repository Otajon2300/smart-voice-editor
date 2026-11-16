// SmartVoiceEditor-Setup.exe: installs the program with its own Python and models from the
// SmartVoiceEditor.data.001, .002, ... files next to it. Needs no internet and no administrator rights.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

namespace SmartVoice
{
    sealed class SetupForm : Form
    {
        const string Prefix = "SmartVoiceEditor/";
        readonly TextBox folder = new TextBox();
        readonly Button browse = new Button(), install = new Button();
        readonly ProgressBar bar = new ProgressBar();
        readonly Label status = new Label();
        readonly string data;
        bool working;

        SetupForm()
        {
            Text = "Smart Voice Editor — o'rnatish (otashDEV)";
            ClientSize = new Size(560, 230);
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Segoe UI", 9.5f);
            data = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "SmartVoiceEditor.data");

            Label head = new Label { Text = "Smart Voice Editor — Premiere Pro uchun ovoz tozalash paneli", Location = new Point(16, 14), AutoSize = true, Font = new Font(Font, FontStyle.Bold) };
            Label where = new Label { Text = "O'rnatish papkasi (internet va administrator huquqi kerak emas):", Location = new Point(16, 46), AutoSize = true };
            folder.Location = new Point(16, 68); folder.Width = 430;
            folder.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SmartVoiceEditor");
            browse.Text = "Tanlash…"; browse.Location = new Point(454, 66); browse.Width = 90;
            browse.Click += delegate
            {
                using (FolderBrowserDialog d = new FolderBrowserDialog())
                    if (d.ShowDialog(this) == DialogResult.OK) folder.Text = Path.Combine(d.SelectedPath, "SmartVoiceEditor");
            };
            bar.Location = new Point(16, 108); bar.Width = 528; bar.Maximum = 1000;
            status.Location = new Point(16, 138); status.Size = new Size(528, 44);
            status.Text = "Premiere Pro'ni yoping va «O'rnatish» tugmasini bosing.";
            install.Text = "O'rnatish"; install.Location = new Point(424, 190); install.Width = 120; install.Height = 30;
            install.Click += delegate { Start(); };
            Controls.AddRange(new Control[] { head, where, folder, browse, bar, status, install });
            FormClosing += delegate(object s, FormClosingEventArgs e) { if (working) e.Cancel = true; };
        }

        void Report(string text, int progress)
        {
            if (InvokeRequired) { BeginInvoke(new Action<string, int>(Report), text, progress); return; }
            if (text != null) status.Text = text;
            if (progress >= 0) bar.Value = Math.Min(1000, progress);
        }

        void Done(bool ok, string text)
        {
            if (InvokeRequired) { BeginInvoke(new Action<bool, string>(Done), ok, text); return; }
            working = false; status.Text = text; install.Enabled = true; browse.Enabled = true; folder.Enabled = true;
            if (ok) { install.Text = "Yopish"; install.Click += delegate { Close(); }; bar.Value = 1000; }
            MessageBox.Show(this, text, Text, MessageBoxButtons.OK, ok ? MessageBoxIcon.Information : MessageBoxIcon.Error);
        }

        void Start()
        {
            if (working) return;
            if (install.Text == "Yopish") return;
            string target = folder.Text.Trim();
            if (target.Length < 4 || !Path.IsPathRooted(target)) { MessageBox.Show(this, "Papka yo'lini to'liq kiriting."); return; }
            working = true; install.Enabled = false; browse.Enabled = false; folder.Enabled = false;
            Thread worker = new Thread(delegate()
            {
                try { Run(Path.GetFullPath(target)); }
                catch (Exception e) { Done(false, "O'rnatishda xato: " + e.Message); }
            });
            worker.IsBackground = true; worker.Start();
        }

        // A backend of an earlier installation keeps its Python files open: stop it first.
        static void StopBackend(string target)
        {
            try
            {
                string config = File.ReadAllText(Path.Combine(target, ".runtime.json"));
                Match m = Regex.Match(config, "\"pid\"\\s*:\\s*(\\d+)");
                if (!m.Success) return;
                Process p = Process.GetProcessById(int.Parse(m.Groups[1].Value));
                if (p.MainModule.FileName.StartsWith(target, StringComparison.OrdinalIgnoreCase)) { p.Kill(); p.WaitForExit(5000); }
            }
            catch (Exception) { }
        }

        void Run(string target)
        {
            Report("O'rnatish fayllari tekshirilmoqda…", 0);
            using (PartReader input = new PartReader(data))
            using (ZipArchive zip = new ZipArchive(input, ZipArchiveMode.Read))
            {
                long total = 0, done = 0;
                foreach (ZipArchiveEntry e in zip.Entries) total += e.Length;
                string drive = Path.GetPathRoot(target);
                long free = new DriveInfo(drive).AvailableFreeSpace;
                if (free < total + (500L << 20))
                    throw new IOException(string.Format("{0} diskda joy yetmaydi: kerak {1:0.0} GB, bo'sh {2:0.0} GB.", drive, (total + (500L << 20)) / 1073741824.0, free / 1073741824.0));
                StopBackend(target);
                Directory.CreateDirectory(target);
                string root = target.TrimEnd('\\') + "\\";
                byte[] buffer = new byte[1 << 20];
                foreach (ZipArchiveEntry e in zip.Entries)
                {
                    if (!e.FullName.StartsWith(Prefix) || e.FullName.EndsWith("/")) continue;
                    string path = Path.GetFullPath(Path.Combine(target, e.FullName.Substring(Prefix.Length).Replace('/', '\\')));
                    if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new IOException("Paket buzilgan: " + e.FullName);
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    Report("Nusxalanmoqda: " + e.FullName.Substring(Prefix.Length), -1);
                    string draft = path + ".partial";
                    using (Stream source = e.Open())
                    using (FileStream output = new FileStream(draft, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20))
                    {
                        int n;
                        while ((n = source.Read(buffer, 0, buffer.Length)) > 0)
                        {
                            output.Write(buffer, 0, n);
                            done += n;
                            Report(null, (int)(done * 950 / Math.Max(1, total)));
                        }
                    }
                    if (File.Exists(path)) File.Delete(path);
                    File.Move(draft, path);
                    File.SetLastWriteTime(path, e.LastWriteTime.DateTime);
                }
            }

            Report("Panel Premiere Pro'ga ulanmoqda…", 960);
            string script = Path.Combine(target, "install-panel.ps1");
            ProcessStartInfo info = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"");
            info.UseShellExecute = false; info.CreateNoWindow = true; info.RedirectStandardOutput = true; info.RedirectStandardError = true;
            info.WorkingDirectory = target;
            using (Process p = Process.Start(info))
            {
                string output = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0) throw new Exception("panel ulanmadi.\r\n" + output.Trim());
            }
            Done(true, "O'rnatish tugadi.\r\nPremiere Pro'ni oching: Window → Extensions → Smart Voice Editor.\r\nPapka: " + target);
        }

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.Run(new SetupForm());
        }
    }
}
