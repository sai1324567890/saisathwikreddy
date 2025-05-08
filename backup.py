import os
import json
import glob
from datetime import datetime, timedelta
import re
import tkinter as tk
from tkinter import messagebox, ttk

def find_config_file(filename="conf.json"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, filename)
    if os.path.exists(config_path):
        return config_path
    else:
        raise FileNotFoundError(f"Configuration file '{filename}' not found in {script_dir}")

def load_config():
    config_path = find_config_file()
    print(f"Loading configuration from {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    validate_config(config)
    
    days_config = config.get("Number_of_days_Increment_and_Decrement")
    if days_config is not None and str(days_config).strip() != "":
        getting = str(days_config)
        if not (getting.startswith('+') or getting.startswith('-')):
            getting = '+' + getting
        sign = getting[0]
        number = int(getting[1:])
        print(f"Sign: {sign}")
        print(f"Number: {number}")
        config['days_sign'] = sign
        config['days_number'] = number
    return config

def validate_config(config):
    def check_length(field, value, max_length):
        if value and len(str(value)) > max_length:
            raise ValueError(f"Error: '{field}' exceeds max length of {max_length} characters! Found: '{value}'")

    def check_date_format(field, value):
        if value:
            if not re.match(r'^\d{8}$', str(value)):
                raise ValueError(f"Error: '{field}' must be exactly 8 numeric characters (YYYYMMDD format). Found: '{value}'")
            try:
                datetime.strptime(str(value), '%Y%m%d')
            except ValueError:
                raise ValueError(f"Error: '{field}' contains an invalid date. Expected format: YYYYMMDD, Found: '{value}'")

    def validate_po1_quantity(field, value):
        if value:
            try:
                qty = int(value)
                if not (0 <= qty <= 10):
                    raise ValueError(f"Error: '{field}' must be between 0 and 10. Found: '{value}'")
            except ValueError as e:
                if "must be between 0 and 10" in str(e):
                    raise
                raise ValueError(f"Error: '{field}' must be a valid number between 0 and 10. Found: '{value}'")

    fields_to_check = [
        'ISA_Sender_ID',
        'ISA_Receiver_ID',
        'GS_Sender_ID',
        'GS_Receiver_ID'
    ]

    for field in fields_to_check:
        value = config[field]
        if value in ['0', '00', '000', 0]:
            raise ValueError(f"Error: '{field}' cannot be {value}!")

    validate_po1_quantity("First_PO1_Quantity", config.get("First_PO1_Quantity"))
    validate_po1_quantity("Second_PO1_Quantity", config.get("Second_PO1_Quantity"))

    check_length("ISA_Sender_ID", config.get("ISA_Sender_ID"), 15)
    check_length("ISA_Receiver_ID", config.get("ISA_Receiver_ID"), 15)
    check_length("GS_Sender_ID", config.get("GS_Sender_ID"), 15)
    check_length("GS_Receiver_ID", config.get("GS_Receiver_ID"), 15)
    check_date_format("dtm_date", config.get("dtm_date"))
    check_length("po_number", config.get("po_number"), 22)

    print("Configuration validation passed!")

def pad_isa_field(value):
    return str(value).ljust(15)[:15]

def adjust_date(date_str, config, segment_type):
    date_str = date_str.strip().rstrip('~')
    if 'days_sign' in config and 'days_number' in config:
        if date_str and re.match(r'^\d{8}$', date_str):
            try:
                adjustment = config['days_number'] if config['days_sign'] == '+' else -config['days_number']
                original_date = datetime.strptime(date_str, '%Y%m%d')
                adjusted_date = original_date + timedelta(days=adjustment)
                new_date = adjusted_date.strftime('%Y%m%d')
                print(f"Updating {segment_type} Date: {date_str} → {new_date} (Adjusted by {config['days_sign']}{config['days_number']} days)")
                return new_date
            except ValueError:
                print(f"Warning: Invalid {segment_type} date '{date_str}' skipped")
        else:
            print(f"Warning: {segment_type} date '{date_str}' is not a valid 8-digit date, skipping adjustment")
    else:
        print(f"Keeping original {segment_type} date: {date_str} (no day adjustment specified)")
    return date_str

class EDIEditorGUI:
    def __init__(self, root, po1_segments, config, content, is_bulk_processing, file_counter):
        self.root = root
        self.po1_segments = po1_segments
        self.config = config
        self.content = content
        self.is_bulk_processing = is_bulk_processing
        self.file_counter = file_counter
        self.selected_segments = []
        self.element_entries = []
        self.order_vars = []
        self.root.title("EDI PO1 Segment Editor")
        
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollable canvas for PO1 segments
        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Populate PO1 segments with checkboxes
        self.check_vars = []
        for i, segment in enumerate(self.po1_segments, 1):
            var = tk.BooleanVar()
            self.check_vars.append(var)
            chk = ttk.Checkbutton(
                self.scrollable_frame,
                text=f"PO1 Sequence {i}: {segment}",
                variable=var,
                command=self.update_selection
            )
            chk.grid(row=i, column=0, sticky=tk.W, pady=2)
        
        # Frame for editing selected segments
        self.edit_frame = ttk.LabelFrame(self.main_frame, text="Edit Selected PO1 Segments", padding="10")
        self.edit_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Buttons
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.E))
        
        ttk.Button(self.button_frame, text="Apply Changes", command=self.apply_changes).grid(row=0, column=0, padx=5)
        ttk.Button(self.button_frame, text="Cancel", command=self.root.destroy).grid(row=0, column=1, padx=5)
        
        # Configure grid weights
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        
    def update_selection(self):
        # Clear previous edit fields
        for widget in self.edit_frame.winfo_children():
            widget.destroy()
        
        self.selected_segments = [(i+1, seg) for i, (seg, var) in enumerate(zip(self.po1_segments, self.check_vars)) if var.get()]
        self.element_entries = []
        self.order_vars = []
        
        if not self.selected_segments:
            ttk.Label(self.edit_frame, text="No segments selected.").grid(row=0, column=0)
            return
        
        # Create edit fields for each selected segment
        element_indices = [2, 6, 7, 8, 9, 10, 11, 12, 13]  # Quantity, UP, etc.
        element_names = ["Quantity", "UP", "Qualifier1", "VA", "Qualifier2", "CB", "Qualifier3", "BO", "Extra"]
        
        for i, (seq_num, segment) in enumerate(self.selected_segments):
            parts = segment.split('*')
            ttk.Label(self.edit_frame, text=f"PO1 Sequence {seq_num}").grid(row=i*2, column=0, sticky=tk.W)
            
            # Order selection
            order_var = tk.StringVar(value=str(i+1))
            self.order_vars.append(order_var)
            ttk.Label(self.edit_frame, text="Position:").grid(row=i*2, column=1, sticky=tk.W)
            ttk.Entry(self.edit_frame, textvariable=order_var, width=5).grid(row=i*2, column=2, sticky=tk.W)
            
            # Element edit fields
            entries = {}
            for j, idx in enumerate(element_indices):
                if idx < len(parts):
                    ttk.Label(self.edit_frame, text=element_names[j]).grid(row=i*2+1, column=j*2, sticky=tk.W)
                    entry = ttk.Entry(self.edit_frame, width=15)
                    entry.insert(0, parts[idx])
                    entry.grid(row=i*2+1, column=j*2+1, sticky=tk.W)
                    entries[idx] = entry
            self.element_entries.append(entries)
        
    def validate_quantity(self, value):
        try:
            qty = int(value)
            if not (0 <= qty <= 10):
                return False, f"Quantity must be between 0 and 10. Found: {value}"
            return True, ""
        except ValueError:
            return False, f"Invalid quantity: {value}"

    def apply_changes(self):
        # Validate inputs
        for i, entries in enumerate(self.element_entries):
            qty_valid, qty_error = self.validate_quantity(entries[2].get())
            if not qty_valid:
                messagebox.showerror("Validation Error", f"PO1 Sequence {self.selected_segments[i][0]}: {qty_error}")
                return
        
        # Validate order positions
        try:
            new_order = [int(var.get()) for var in self.order_vars]
            if sorted(new_order) != list(range(1, len(new_order) + 1)):
                messagebox.showerror("Validation Error", "Invalid position order. Use unique numbers from 1 to " + str(len(new_order)))
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Invalid position input. Enter numbers only.")
            return
        
        # Reorder segments
        reordered_segments = [None] * len(self.selected_segments)
        reordered_entries = [None] * len(self.element_entries)
        for old_pos, new_pos in enumerate(new_order, 1):
            reordered_segments[new_pos - 1] = self.selected_segments[old_pos - 1]
            reordered_entries[new_pos - 1] = self.element_entries[old_pos - 1]
        
        # Update content
        updated_content = self.modify_edi_file(reordered_segments, reordered_entries)
        
        # Save output
        self.save_output(updated_content)
        messagebox.showinfo("Success", "File processed and saved successfully!")
        self.root.destroy()

    def modify_edi_file(self, selected_segments, new_elements_list):
        is_single_line = '\n' not in self.content and '*' in self.content
        if is_single_line:
            lines = [line.strip().rstrip('~') for line in self.content.split('~') if line.strip()]
        else:
            lines = [line.strip().rstrip('~') for line in self.content.strip().split('\n') if line.strip()]
        
        try:
            ctt_index = next(i for i, line in enumerate(lines) if line.startswith('CTT*'))
            ctt_original = lines[ctt_index]
            body_lines = lines[:ctt_index]
            footer_lines = lines[ctt_index:]
        except StopIteration:
            print("Warning: CTT segment not found! Processing entire file as body.")
            body_lines = lines
            footer_lines = []
            ctt_original = None
        
        filtered_body = []
        po1_index = 0
        selected_seq_nums = [seq_num for seq_num, _ in selected_segments]
        selected_po1_lines = [line for _, line in selected_segments]
        selected_po1_index = 0
        
        first_qty = self.config.get("First_PO1_Quantity")
        second_qty = self.config.get("Second_PO1_Quantity")
        
        for line in body_lines:
            if line.startswith('PO1*'):
                po1_index += 1
                if po1_index in selected_seq_nums:
                    parts = selected_po1_lines[selected_po1_index].split('*')
                    parts[1] = str(po1_index)
                    user_elements = new_elements_list[selected_po1_index]
                    for idx, entry in user_elements.items():
                        parts[idx] = entry.get()
                    selected_po1_index += 1
                    filtered_body.append('*'.join(parts))
                else:
                    # Only include unmodified PO1 segments if they were not selected
                    parts = line.split('*')
                    parts[1] = str(po1_index)
                    if po1_index == 1 and first_qty is not None and str(first_qty).strip() != "":
                        parts[2] = str(first_qty)
                    elif po1_index == 2 and second_qty is not None and str(second_qty).strip() != "":
                        parts[2] = str(second_qty)
                    filtered_body.append('*'.join(parts))
            else:
                filtered_body.append(line)
        
        lines = filtered_body + footer_lines
        
        for i, line in enumerate(lines):
            parts = line.split('*')
            if line.startswith('ISA*') and len(parts) > 8:
                sender_id = self.config.get('ISA_Sender_ID', '').strip() or parts[6]
                receiver_id = self.config.get('ISA_Receiver_ID', '').strip() or parts[8]
                parts[6] = pad_isa_field(sender_id)
                parts[8] = pad_isa_field(receiver_id)
                lines[i] = '*'.join(parts)
            
            elif line.startswith('GS*') and len(parts) > 3:
                parts[2] = self.config.get('GS_Sender_ID', '').strip() or parts[2]
                parts[3] = self.config.get('GS_Receiver_ID', '').strip() or parts[3]
                lines[i] = '*'.join(parts)
            
            elif line.startswith('DTM*') and len(parts) > 2:
                parts[2] = adjust_date(parts[2], self.config, "DTM")
                lines[i] = '*'.join(parts)
            
            elif line.startswith('G62*') and len(parts) > 2:
                parts[2] = adjust_date(parts[2], self.config, "G62")
                lines[i] = '*'.join(parts)
            
            elif line.startswith('BEG*') and len(parts) > 3:
                config_po_number = self.config.get('po_number', '').strip()
                if config_po_number:
                    beg_identifier = f"{config_po_number}T{self.file_counter}" if self.is_bulk_processing else config_po_number
                else:
                    beg_identifier = parts[3]
                    if beg_identifier.endswith('T1'):
                        beg_identifier = beg_identifier[:-2]
                parts[3] = beg_identifier
                lines[i] = '*'.join(parts)
            
            elif line.startswith('CTT*'):
                final_po1_count = sum(1 for line in filtered_body if line.startswith('PO1*'))
                if ctt_original:
                    parts = ctt_original.split('*')
                    parts[1] = str(final_po1_count)
                    lines[i] = '*'.join(parts)
                else:
                    lines[i] = f"CTT*{final_po1_count}"
            
            elif line.startswith('SE*') and len(parts) > 1:
                segment_count = len(lines) - 4
                parts[1] = str(segment_count)
                lines[i] = '*'.join(parts)
        
        return '~'.join(lines) + '~' if is_single_line else '\n'.join(line + '~' for line in lines)
    
    def save_output(self, updated_content):
        input_folder = self.config.get('input_folder_path')
        output_folder = self.config.get('output_folder_path')
        input_file = self.config.get('current_file')
        
        os.makedirs(output_folder, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename, file_extension = os.path.splitext(os.path.basename(input_file))
        new_filename = f"{base_filename}_{timestamp}{file_extension}"
        output_file_path = os.path.join(output_folder, new_filename)
        
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            output_file.write(updated_content)
        print(f"Processed & saved: {output_file_path}")

def process_files_and_save(config):
    input_folder = config.get('input_folder_path')
    output_folder = config.get('output_folder_path')

    if not input_folder or not os.path.exists(input_folder):
        raise FileNotFoundError(f"Input folder '{input_folder}' not found!")
    if not output_folder:
        raise ValueError("Output folder path is missing in the configuration!")

    input_files = glob.glob(os.path.join(input_folder, '*.edi')) + glob.glob(os.path.join(input_folder, '*.txt'))
    if not input_files:
        print("No files found in the input folder!")
        return

    is_bulk_processing = len(input_files) > 1
    file_counter = 1

    for file_path in input_files:
        if os.path.isfile(file_path):
            print(f"\nProcessing file: {os.path.basename(file_path)}")
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Extract PO1 segments
            lines = [line.strip().rstrip('~') for line in content.replace('~', '\n').split('\n') if line.strip()]
            po1_segments = [line for line in lines if line.startswith('PO1*')]
            
            if not po1_segments:
                print("No PO1 segments found in the file. Skipping...")
                continue
            
            # Store current file in config for saving
            config['current_file'] = file_path
            
            # Launch GUI
            root = tk.Tk()
            app = EDIEditorGUI(root, po1_segments, config, content, is_bulk_processing, file_counter)
            root.mainloop()
            
            file_counter += 1

if __name__ == '__main__':
    try:
        config = load_config()
        process_files_and_save(config)
    except Exception as e:
        print(f"Error: {str(e)}")