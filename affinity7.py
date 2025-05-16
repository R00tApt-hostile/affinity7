import psutil
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from threading import Thread

class CPUAffinityToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CPU Affinity Tool for Windows 7")
        self.root.geometry("800x600")  # Increased size for better layout
        self.root.resizable(False, False) #prevent window resizing

        # Style
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Use a modern theme

        # Global Variables
        self.pid_affinities = {}
        self.profile_name = tk.StringVar()
        self.selected_pid = tk.IntVar() #keep track of selected process.
        self.available_cores = list(range(psutil.cpu_count(logical=True))) #store available cores

        # Frames
        self.cpu_info_frame = ttk.Frame(self.root)
        self.process_list_frame = ttk.Frame(self.root)
        self.affinity_control_frame = ttk.Frame(self.root)
        self.profile_management_frame = ttk.Frame(self.root)
        self.log_frame = ttk.Frame(self.root) #frame for log

        # Layout using grid
        self.cpu_info_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=10)
        self.process_list_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=10)
        self.affinity_control_frame.grid(row=2, column=0, sticky='nw', padx=10, pady=10)
        self.profile_management_frame.grid(row=2, column=1, sticky='ne', padx=10, pady=10)
        self.log_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=10, pady=10) #log frame

        self.root.grid_rowconfigure(1, weight=1)  # Make process list frame expandable
        self.root.grid_columnconfigure(0, weight=1) # Make column 0 expandable.

        # CPU Info Section
        self.create_cpu_info_section()

        # Process List Section
        self.create_process_list_section()

        # Affinity Control Section
        self.create_affinity_control_section()

        # Profile Management Section
        self.create_profile_management_section()

        # Log Section
        self.create_log_section()

        # Initial population of data
        self.populate_process_list()
        self.get_cpu_topology()

    def create_cpu_info_section(self):
        """Creates the CPU information display."""
        self.cpu_info_label = ttk.Label(self.cpu_info_frame, text="CPU Information", font=('Arial', 12, 'bold'))
        self.cpu_info_label.pack(pady=5)

        self.cpu_topology_text = tk.StringVar()
        self.cpu_info_display = ttk.Label(self.cpu_info_frame, textvariable=self.cpu_topology_text, wraplength=350)
        self.cpu_info_display.pack(padx=10, pady=5)

    def create_process_list_section(self):
        """Creates the process list display."""
        self.process_list_label = ttk.Label(self.process_list_frame, text="Running Processes", font=('Arial', 12, 'bold'))
        self.process_list_label.pack(pady=5)

        self.process_list = ttk.Treeview(self.process_list_frame, cols=('PID', 'Name'), show='headings')
        self.process_list.heading('PID', text='PID')
        self.process_list.heading('Name', text='Name')
        self.process_list.column('PID', width=50, anchor='center')
        self.process_list.column('Name', width=200, anchor='left')
        self.process_list.pack(expand=True, fill='both', padx=10, pady=5)
        self.process_list.bind('<<TreeviewSelect>>', self.on_process_select) #bind select

    def create_affinity_control_section(self):
        """Creates the affinity control section."""
        self.affinity_label = ttk.Label(self.affinity_control_frame, text="Affinity Control", font=('Arial', 12, 'bold'))
        self.affinity_label.pack(pady=5)

        self.core_checkboxes = []
        for i, core_id in enumerate(self.available_cores):
            var = tk.IntVar(value=0)  # 0 for unchecked, 1 for checked
            checkbox = ttk.Checkbutton(self.affinity_control_frame, text=f"Core {core_id}", variable=var)
            checkbox.grid(row=i // 4, column=i % 4, sticky='w', padx=5, pady=2)  # Arrange in a grid
            self.core_checkboxes.append(var)

        self.set_affinity_button = ttk.Button(self.affinity_control_frame, text="Set Affinity", command=self.on_set_affinity)
        self.set_affinity_button.pack(pady=10)

    def create_profile_management_section(self):
        """Creates the profile management section."""
        self.profile_label = ttk.Label(self.profile_management_frame, text="Profile Management", font=('Arial', 12, 'bold'))
        self.profile_label.pack(pady=5)

        self.profile_name_entry = ttk.Entry(self.profile_management_frame, textvariable=self.profile_name)
        self.profile_name_entry.pack(padx=10, pady=5)

        self.save_profile_button = ttk.Button(self.profile_management_frame, text="Save Profile", command=self.on_save_profile)
        self.save_profile_button.pack(pady=5)

        self.load_profile_button = ttk.Button(self.profile_management_frame, text="Load Profile", command=self.on_load_profile)
        self.load_profile_button.pack(pady=5)

    def create_log_section(self):
        """Creates the log section."""
        self.log_label = ttk.Label(self.log_frame, text="Log Messages", font=('Arial', 12, 'bold'))
        self.log_label.pack(pady=5)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=8, state='disabled', wrap=tk.WORD)
        self.log_text.pack(expand=True, fill='both', padx=10, pady=5)
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('info', foreground='black')

    # Helper Functions
    def log_message(self, message, tag='info'):
        """Logs a message to the text widget."""
        self.log_text.config(state='normal')  # Enable editing
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)  # Scroll to the end
        self.log_text.config(state='disabled')  # Disable editing

    def get_cpu_topology(self):
        """Gets and displays CPU topology information."""
        def _get_topology(): #function for thread
            logical_cores = psutil.cpu_count(logical=True)
            physical_cores = psutil.cpu_count(logical=False)
            cpu_info_text = f"Number of Logical Cores: {logical_cores}\n"
            cpu_info_text += f"Number of Physical Cores: {physical_cores}\n"

            if logical_cores > physical_cores:
                cpu_info_text += "Hyperthreading: Enabled (Likely)\n"
                cpu_info_text += "Note: On Windows 7, distinguishing P-cores and E-cores requires manual identification.\n"
                cpu_info_text += "Please refer to your CPU documentation to determine the mapping of logical cores to physical and/or P/E cores.\n"
            else:
                cpu_info_text += "Hyperthreading: Disabled or Not Supported\n"
                cpu_info_text += "Note: On Windows 7, distinguishing P-cores and E-cores requires manual identification.\n"
                cpu_info_text += "Please refer to your CPU documentation.\n"

            cpu_info_text += "Logical Core IDs: " + " ".join(map(str, self.available_cores)) + "\n"
            self.cpu_topology_text.set(cpu_info_text)
        Thread(target=_get_topology).start()

    def populate_process_list(self):
        """Populates the process list."""
        def _populate_list():
            processes = sorted(psutil.process_iter(['pid', 'name']), key=lambda p: p.info['pid'])
            for proc in processes:
                self.process_list.insert('', 'end', values=(proc.info['pid'], proc.info['name']))
        Thread(target=_populate_list).start()

    def on_process_select(self, event):
        """Handles process selection event."""
        selected_item = self.process_list.selection()
        if selected_item:
            pid = int(self.process_list.item(selected_item, 'values')[0])
            self.selected_pid.set(pid)
            self.update_core_checkboxes(pid) #update checkboxes when process is selected.

    def update_core_checkboxes(self, pid):
        """Updates the core checkboxes based on the affinity of the selected process."""
        try:
            process = psutil.Process(pid)
            core_ids = process.cpu_affinity()
            for i, core_id in enumerate(self.available_cores):
                self.core_checkboxes[i].set(1 if core_id in core_ids else 0)
        except psutil.NoSuchProcess:
            self.log_message(f"Error: Process with PID {pid} not found.", 'error')
            for checkbox in self.core_checkboxes:
                checkbox.set(0) #clear all checkboxes if process does not exist
        except psutil.AccessDenied:
            self.log_message("Error: Access denied.  Run as administrator.", 'error')
            for checkbox in self.core_checkboxes:
                checkbox.set(0)  # clear all checkboxes
        except Exception as e:
            self.log_message(f"Error: An unexpected error occurred: {e}", 'error')
            for checkbox in self.core_checkboxes:
                checkbox.set(0)

    def on_set_affinity(self):
        """Sets the CPU affinity for the selected process."""
        pid = self.selected_pid.get()
        if pid == 0:
            messagebox.showerror("Error", "Please select a process from the list.")
            return

        core_ids = [self.available_cores[i] for i, var in enumerate(self.core_checkboxes) if var.get() == 1]
        if not core_ids:
            messagebox.showerror("Error", "Please select at least one core.")
            return

        if set_affinity(pid, core_ids):
            self.log_message(f"Successfully set affinity for PID {pid} to cores: {core_ids}")
            self.pid_affinities[str(pid)] = core_ids  # Update the dictionary
        else:
            self.log_message(f"Failed to set affinity for PID {pid}", 'error')

    def on_save_profile(self):
        """Saves the current CPU affinity settings to a profile file."""
        profile_name = self.profile_name.get()
        if not profile_name:
            messagebox.showerror("Error", "Please enter a profile name.")
            return

        if save_profile(profile_name, self.pid_affinities):
            self.log_message(f"Profile '{profile_name}' saved successfully.")
        else:
            self.log_message(f"Failed to save profile '{profile_name}'", 'error')

    def on_load_profile(self):
        """Loads a CPU affinity profile from a file."""
        profile_name = self.profile_name.get()
        if not profile_name:
            messagebox.showerror("Error", "Please enter a profile name.")
            return

        loaded_profile = load_profile(profile_name)
        if loaded_profile:
            self.pid_affinities = loaded_profile.copy() #update current affinites
            for pid_str, core_ids in loaded_profile.items():
                pid = int(pid_str)
                set_affinity(pid, core_ids) #also set the affnity.
                self.log_message(f"Loaded affinity settings from profile '{profile_name}'")
            self.populate_process_list() #refresh process list.
            if self.selected_pid.get() != 0:
                self.update_core_checkboxes(self.selected_pid.get()) #update checkboxes.
        else:
            self.log_message(f"Failed to load profile '{profile_name}'", 'error')

def set_affinity(pid, core_ids):
    """Sets the CPU affinity for a given process with comprehensive error handling."""
    if not isinstance(pid, int) or pid <= 0:
        print(f"Error: Invalid PID: {pid}.  PID must be a positive integer.")
        return False

    if not isinstance(core_ids, list) or not all(isinstance(core, int) and core >= 0 for core in core_ids):
        print(f"Error: Invalid core IDs: {core_ids}.  Core IDs must be a list of non-negative integers.")
        return False

    try:
        process = psutil.Process(pid)
        process.cpu_affinity(core_ids)
        return True  # Indicate success
    except psutil.NoSuchProcess:
        print(f"Error: Process with PID {pid} not found.")
        return False
    except psutil.AccessDenied:
        print(f"Error: Access denied.  Run this script as administrator to set process affinities.")
        return False
    except OSError as e:
        print(f"Error: OS error occurred: {e}")
        return False
    except Exception as e:
        print(f"Error: An unexpected error occurred: {e}")
        return False

def save_profile(profile_name, pid_affinities):
    """Saves a CPU affinity profile to a JSON file with error handling."""
    if not profile_name:
        print("Error: Profile name cannot be empty.")
        return False
    if not isinstance(pid_affinities, dict):
        print("Error: Invalid pid_affinities data type.  Must be a dictionary.")
        return False

    try:
        with open(f"{profile_name}.json", "w") as f:
            json.dump(pid_affinities, f, indent=4)
        return True
    except (IOError, OSError) as e:
        print(f"Error: I/O error occurred while saving profile: {e}")
        return False
    except TypeError as e:
        print(f"Error: Type error occurred while saving profile: {e}")
        return False
    except Exception as e:
        print(f"Error: An unexpected error occurred: {e}")
        return False

def load_profile(profile_name):
    """Loads a CPU affinity profile from a JSON file with error handling."""
    if not profile_name:
        print("Error: Profile name cannot be empty.")
        return {}  # Return empty dict on error

    try:
        with open(f"{profile_name}.json", "r") as f:
            pid_affinities = json.load(f)  # Load the entire dictionary
        return pid_affinities  # Return the loaded data
    except FileNotFoundError:
        print(f"Error: Profile file '{profile_name}' not found.")
        return {}  # Return empty dict on error
    except (IOError, OSError) as e:
        print(f"Error: I/O error occurred while loading profile: {e}")
        return {}  # Return empty dict on error
    except json.JSONDecodeError as e:
        print(f"Error: JSON decode error: {e}.  The profile file may be corrupted.")
        return {}  # Return empty dict on error
    except Exception as e:
        print(f"Error: An unexpected error occurred: {e}")
        return {}  # Return empty dict on error

if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("WARNING: This script should be run as administrator to set process affinities.")
        print("         Some features may be limited without administrator privileges.")
    root = tk.Tk()
    app = CPUAffinityToolGUI(root)
    root.mainloop()

