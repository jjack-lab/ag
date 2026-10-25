using System;
using System.Diagnostics;
using System.IO;

internal static class Program
{
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string script = Path.Combine(root, "\u542f\u52a8\u9879\u76ee.bat");
        if (!File.Exists(script))
        {
            Console.Error.WriteLine("Start script missing: " + script);
            return 1;
        }

        if (args.Length == 1 && args[0] == "--check")
        {
            Console.WriteLine(script);
            return 0;
        }
        if (args.Length != 0)
        {
            Console.Error.WriteLine("Usage: XingMuLauncher.exe [--check]");
            return 2;
        }

        using (Process process = new Process())
        {
            process.StartInfo.FileName = Path.Combine(Environment.SystemDirectory, "cmd.exe");
            process.StartInfo.Arguments = "/d /c \"\"" + script + "\"\"";
            process.StartInfo.WorkingDirectory = root;
            process.StartInfo.UseShellExecute = false;
            try
            {
                process.Start();
                process.WaitForExit();
                return process.ExitCode;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine("Unable to launch website: " + error.Message);
                Console.WriteLine("Press Enter to close.");
                Console.ReadLine();
                return 1;
            }
        }
    }
}
