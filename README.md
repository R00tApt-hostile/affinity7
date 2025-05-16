CPU Affinity Tool for Windows 7

A utility to manage process CPU affinity on Windows 7.

This tool provides a graphical interface to view running processes and set their CPU affinity.  This can be helpful for manually optimizing performance, especially on systems with heterogeneous CPU architectures (though full optimization is limited by Windows 7's kernel).

Features:

    CPU Topology Display: Shows the number of logical and physical cores.

    Process List: Displays a list of running processes with their PIDs and names.

    CPU Affinity Control: Allows you to select which cores a process can run on.

    Profile Management: Save and load CPU affinity profiles.

    Logging: Displays informative messages and errors.

Limitations:

    Windows 7 Kernel: Windows 7 lacks native support for distinguishing between different CPU core types (e.g., P-cores and E-cores). This tool provides manual affinity control but cannot fully replicate the intelligent scheduling of modern operating systems.

    Manual Configuration: Users must manually determine the mapping of logical cores to physical/P/E cores using their CPU documentation.

    Administrator Privileges: Setting CPU affinity requires administrator privileges.

Requirements:

    Windows 7

    Python 3

    psutil library (pip install psutil)

How to Use:

    Download the script.

    Run the script as an administrator.

    View CPU topology information.

    Select a process from the list.

    Select the cores you want the process to use.

    Save and load profiles for different use cases.

Disclaimer:

This tool provides a workaround for a limitation in Windows 7. Optimal performance on modern CPUs may not be achievable. Use with caution.
