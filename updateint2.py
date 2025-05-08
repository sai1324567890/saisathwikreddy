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
                    raise ValueError(f"Error: '{field}' must be between 0 and 10. Found: {value}")
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

def modify_edi_file(content, config, selected_segments=None, new_elements_list=None, is_bulk_processing=False, file_counter=None):
    selected_segments = selected_segments or []
    new_elements_list = new_elements_list or []
    
    is_single_line = '\n' not in content and '*' in content
    if is_single_line:
        print("Detected single-line EDI file. Splitting into segments...")
        lines = [line.strip().rstrip('~') for line in content.split('~') if line.strip()]
    else:
        lines = [line.strip().rstrip('~') for line in content.strip().split('\n') if line.strip()]

    # Collect PO1 segments and their related segments
    po1_groups = []
    current_group = []
    po1_index = 0
    related_segments = ['CTP*', 'PID*', 'PO4*', 'SDQ*']

    for line in lines:
        if line.startswith('PO1*'):
            if current_group:
                po1_groups.append((po1_index, current_group))
            po1_index += 1
            current_group = [line]
        elif any(line.startswith(seg) for seg in related_segments) and current_group and current_group[0].startswith('PO1*'):
            current_group.append(line)
        else:
            if current_group:
                po1_groups.append((po1_index, current_group))
                current_group = []
            current_group.append(line)

    if current_group:
        if current_group[0].startswith('PO1*'):
            po1_groups.append((po1_index, current_group))
        else:
            po1_groups.append((0, current_group))

    # Process segments
    selected_seq_nums = [seq_num for seq_num, _ in selected_segments]
    new_elements_dict = {seq_num: elements for seq_num, elements in new_elements_list}
    filtered_lines = []
    po1_counter = 0

    for index, group in po1_groups:
        if group[0].startswith('PO1*'):
            if selected_segments:
                if index in selected_seq_nums:
                    po1_counter += 1
                    po1_line = group[0]
                    parts = po1_line.split('*')
                    parts[1] = str(po1_counter)
                    print(f"Assigned serial number {po1_counter} to selected PO1 segment (original sequence {index})")
                    if index in new_elements_dict:
                        for idx, value in new_elements_dict[index].items():
                            if value is not None:
                                parts[idx] = value
                                print(f"Applying user element for PO1 {po1_counter} at position {idx}: {value}")
                    first_qty = config.get("First_PO1_Quantity")
                    second_qty = config.get("Second_PO1_Quantity")
                    if po1_counter == 1 and first_qty is not None and str(first_qty).strip() != "":
                        print(f"Using config First_PO1_Quantity: {first_qty}")
                        parts[2] = str(first_qty)
                    elif po1_counter == 2 and second_qty is not None and str(second_qty).strip() != "":
                        print(f"Using config Second_PO1_Quantity: {second_qty}")
                        parts[2] = str(second_qty)
                    group[0] = '*'.join(parts)
                    filtered_lines.extend(group)
            else:
                filtered_lines.extend(group)
        else:
            modified_group = []
            for line in group:
                parts = line.split('*')
                if line.startswith('ISA*') and len(parts) > 8:
                    sender_id = config.get('ISA_Sender_ID', '').strip() or parts[6]
                    receiver_id = config.get('ISA_Receiver_ID', '').strip() or parts[8]
                    parts[6] = pad_isa_field(sender_id)
                    parts[8] = pad_isa_field(receiver_id)
                    modified_group.append('*'.join(parts))
                elif line.startswith('GS*') and len(parts) > 3:
                    parts[2] = config.get('GS_Sender_ID', '').strip() or parts[2]
                    parts[3] = config.get('GS_Receiver_ID', '').strip() or parts[3]
                    modified_group.append('*'.join(parts))
                elif line.startswith('DTM*') and len(parts) > 2:
                    parts[2] = adjust_date(parts[2], config, "DTM")
                    modified_group.append('*'.join(parts))
                elif line.startswith('G62*') and len(parts) > 2:
                    parts[2] = adjust_date(parts[2], config, "G62")
                    modified_group.append('*'.join(parts))
                elif line.startswith('BEG*') and len(parts) > 3:
                    config_po_number = config.get('po_number', '').strip()
                    if config_po_number:
                        if is_bulk_processing:
                            beg_identifier = f"{config_po_number}T{file_counter}"
                        else:
                            beg_identifier = config_po_number
                    else:
                        beg_identifier = parts[3]
                        if beg_identifier.endswith('T1'):
                            beg_identifier = beg_identifier[:-2]
                    parts[3] = beg_identifier
                    print(f"Updating BEG Segment PO Number: {parts[3]}")
                    modified_group.append('*'.join(parts))
                elif line.startswith('CTT*'):
                    final_po1_count = sum(1 for l in filtered_lines if l.startswith('PO1*')) + sum(1 for l in group if l.startswith('PO1*'))
                    parts[1] = str(final_po1_count)
                    modified_group.append('*'.join(parts))
                    print(f"Updating CTT count to: {final_po1_count}")
                elif line.startswith('SE*') and len(parts) > 1:
                    segment_count = sum(1 for l in filtered_lines if not l.startswith(('ISA*', 'GS*', 'GE*', 'IEA*'))) + sum(1 for l in group if not l.startswith(('ISA*', 'GS*', 'GE*', 'IEA*')))
                    parts[1] = str(segment_count)
                    print(f"Updating SE Segment Count: {parts[1]}")
                    modified_group.append('*'.join(parts))
                else:
                    modified_group.append(line)
            filtered_lines.extend(modified_group)

    final_po1_count = sum(1 for line in filtered_lines if line.startswith('PO1*'))
    if not any(line.startswith('CTT*') for line in filtered_lines):
        filtered_lines.append(f"CTT*{final_po1_count}")
        print(f"Adding CTT segment with count: {final_po1_count}")
    if not any(line.startswith('SE*') for line in filtered_lines):
        segment_count = sum(1 for line in filtered_lines if not line.startswith(('ISA*', 'GS*', 'GE*', 'IEA*')))
        filtered_lines.append(f"SE*{segment_count}*0001")
        print(f"Adding SE segment with count: {segment_count}")

    if is_single_line:
        return '~'.join(filtered_lines) + '~'
    else:
        return '\n'.join(line + '~' for line in filtered_lines)

class EDIEditorGUI:
    def __init__(self, root, po1_segments, config, content, input_file, is_bulk_processing, file_counter):
        self.root = root
        self.po1_segments = po1_segments
        self.config = config
        self.content = content
        self.input_file = input_file
        self.is_bulk_processing = is_bulk_processing
        self.file_counter = file_counter
        self.selected_segments = []
        self.element_entries = []
        self.order_vars = []
        self.root.title("EDI PO1 Segment Editor")
        
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollable frame for PO1 selection
        self.selection_frame = ttk.LabelFrame(self.main_frame, text="Select PO1 Segments", padding="10")
        self.selection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.selection_canvas = tk.Canvas(self.selection_frame)
        self.selection_v_scrollbar = ttk.Scrollbar(self.selection_frame, orient="vertical", command=self.selection_canvas.yview)
        self.selection_h_scrollbar = ttk.Scrollbar(self.selection_frame, orient="horizontal", command=self.selection_canvas.xview)
        self.selection_scrollable_frame = ttk.Frame(self.selection_canvas)
        
        self.selection_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.selection_canvas.configure(scrollregion=self.selection_canvas.bbox("all"))
        )
        
        self.selection_canvas.create_window((0, 0), window=self.selection_scrollable_frame, anchor="nw")
        self.selection_canvas.configure(yscrollcommand=self.selection_v_scrollbar.set, xscrollcommand=self.selection_h_scrollbar.set)
        
        self.selection_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.selection_v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.selection_h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        self.check_vars = []
        for i, segment in enumerate(self.po1_segments, 1):
            var = tk.BooleanVar()
            self.check_vars.append(var)
            chk = ttk.Checkbutton(
                self.selection_scrollable_frame,
                text=f"PO1 Sequence {i}: {segment}",
                variable=var,
                command=self.update_selection
            )
            chk.grid(row=i, column=0, sticky=tk.W, pady=2)
        
        
        # Scrollable frame for editing selected PO1 segments
        self.edit_frame = ttk.LabelFrame(self.main_frame, text="Edit Selected PO1 Segments", padding="10")
        self.edit_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.edit_canvas = tk.Canvas(self.edit_frame)
        self.edit_v_scrollbar = ttk.Scrollbar(self.edit_frame, orient="vertical", command=self.edit_canvas.yview)
        self.edit_h_scrollbar = ttk.Scrollbar(self.edit_frame, orient="horizontal", command=self.edit_canvas.xview)
        self.edit_scrollable_frame = ttk.Frame(self.edit_canvas)
        
        self.edit_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.edit_canvas.configure(scrollregion=self.edit_canvas.bbox("all"))
        )
        
        self.edit_canvas.create_window((0, 0), window=self.edit_scrollable_frame, anchor="nw")
        self.edit_canvas.configure(yscrollcommand=self.edit_v_scrollbar.set, xscrollcommand=self.edit_h_scrollbar.set)
        
        self.edit_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.edit_v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.edit_h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.E))
        
        ttk.Button(self.button_frame, text="Apply Changes", command=self.apply_changes).grid(row=0, column=0, padx=5)
        ttk.Button(self.button_frame, text="Cancel", command=self.root.destroy).grid(row=0, column=1, padx=5)
        
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.selection_frame.columnconfigure(0, weight=1)
        self.selection_frame.rowconfigure(0, weight=1)
        self.edit_frame.columnconfigure(0, weight=1)
        self.edit_frame.rowconfigure(0, weight=1)
        
        # Initial update to show "No segments selected" message
        self.update_selection()

    def update_selection(self):
        for widget in self.edit_scrollable_frame.winfo_children():
            widget.destroy()
        
        self.selected_segments = [(i+1, seg) for i, (seg, var) in enumerate(zip(self.po1_segments, self.check_vars)) if var.get()]
        self.element_entries = []
        self.order_vars = []
        
        if not self.selected_segments:
            ttk.Label(self.edit_scrollable_frame, text="No segments selected.").grid(row=0, column=0)
            return
        
        element_indices = [2, 6, 7, 8, 9, 10, 11, 12, 13]
        element_names = ["Quantity", "UP", "Qualifier1", "VA", "Qualifier2", "CB", "Qualifier3", "BO", "Extra"]
        
        for i, (seq_num, segment) in enumerate(self.selected_segments):
            parts = segment.split('*')
            ttk.Label(self.edit_scrollable_frame, text=f"PO1 Sequence {seq_num}").grid(row=i*2, column=0, sticky=tk.W)
            
            order_var = tk.StringVar(value=str(i+1))
            self.order_vars.append(order_var)
            ttk.Label(self.edit_scrollable_frame, text="Position:").grid(row=i*2, column=1, sticky=tk.W)
            ttk.Entry(self.edit_scrollable_frame, textvariable=order_var, width=5).grid(row=i*2, column=2, sticky=tk.W)
            
            entries = {}
            
            for j, idx in enumerate(element_indices):
                if idx < len(parts):
                    ttk.Label(self.edit_scrollable_frame, text=element_names[j]).grid(row=i*2+1, column=j*2, sticky=tk.W)
                    entry = ttk.Entry(self.edit_scrollable_frame, width=15)
                    entry.insert(0, parts[idx])
                    entry.grid(row=i*2+1, column=j*2+1, sticky=tk.W)
                    entries[idx] = entry
            self.element_entries.append(entries)
        
    def validate_quantity(self, value):
        try:
            qty = int(value)
            if not (0 <= qty <= 10):
                return False, f"Quantity must be between 0 and 10: {value}"
            return True, ""
        except ValueError:
            return False, f"Invalid quantity: {value}"

    def save_output(self, updated_content):
        output_folder = self.config.get('output_folder_path')
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        input_filename = os.path.basename(self.input_file)
        output_filename = f"processed_{input_filename}" if not self.is_bulk_processing else f"processed_{self.file_counter}_{input_filename}"
        output_path = os.path.join(output_folder, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print(f"Saved output to: {output_path}")

    def apply_changes(self):
        # Validate quantities
        for i, entries in enumerate(self.element_entries):
            qty_valid, qty_error = self.validate_quantity(entries[2].get())
            if not qty_valid:
                messagebox.showerror("Validation Error", f"PO1 Sequence {self.selected_segments[i][0]}: {qty_error}")
                return
        
        # Validate order positions
        try:
            new_order = [int(var.get()) for var in self.order_vars]
            if sorted(new_order) != list(range(1, len(new_order) + 1)):
                messagebox.showerror("Validation Error", f"Invalid position order. Use unique numbers from 1 to {len(new_order)}")
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Invalid position input. Enter numbers only.")
            return
        
        # Reorder segments and entries
        reordered_segments = [None] * len(self.selected_segments)
        reordered_entries = [None] * len(self.element_entries)
        for old_pos, new_pos in enumerate(new_order, 1):
            reordered_segments[new_pos - 1] = self.selected_segments[old_pos - 1]
            reordered_entries[new_pos - 1] = self.element_entries[old_pos - 1]
        
        # Prepare new elements list
        new_elements_list = []
        for seq_num, _ in reordered_segments:
            entries = reordered_entries[reordered_segments.index((seq_num, self.po1_segments[seq_num-1]))]
            elements = {idx: entry.get() for idx, entry in entries.items()}
            new_elements_list.append((seq_num, elements))
        
        # Update content
        updated_content = modify_edi_file(
            self.content, 
            self.config, 
            reordered_segments, 
            new_elements_list, 
            self.is_bulk_processing, 
            self.file_counter
        )
        
        # Save output
        self.save_output(updated_content)
        messagebox.showinfo("Success", "File processed and saved successfully!")
        self.root.destroy()

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
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                # Extract PO1 segments
                lines = [line.strip().rstrip('~') for line in content.replace('~', '\n').split('\n') if line.strip()]
                po1_segments = [line for line in lines if line.startswith('PO1*')]

                if not po1_segments:
                    print("No PO1 segments found in the file. Processing without GUI...")
                    updated_content = modify_edi_file(
                        content,
                        config,
                        is_bulk_processing=is_bulk_processing,
                        file_counter=file_counter
                    )
                    
                    # Save output
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    base_filename, file_extension = os.path.splitext(os.path.basename(file_path))
                    output_filename = f"processed_{base_filename}_{timestamp}{file_extension}"
                    output_file_path = os.path.join(output_folder, output_filename)

                    if content != updated_content:
                        if not os.path.exists(output_folder):
                            os.makedirs(output_folder)
                        with open(output_file_path, 'w', encoding='utf-8') as output_file:
                            output_file.write(updated_content)
                        print(f"Processed & saved: {output_file_path}")
                    else:
                        print(f"No changes needed: {os.path.basename(file_path)}")
                    file_counter += 1
                    continue

                # Determine file type
                file_type = "Unknown"
                for line in lines:
                    if line.startswith('ST*'):
                        parts = line.split('*')
                        if len(parts) > 1:
                            transaction_set = parts[1]
                            if transaction_set == '850':
                                file_type = '850 (Purchase Order)'
                            elif transaction_set == '875':
                                file_type = '875 (Grocery Products Purchase Order)'
                        break
                print(f"File type: {file_type}")

                # Launch GUI
                root = tk.Tk()
                app = EDIEditorGUI(root, po1_segments, config, content, file_path, is_bulk_processing, file_counter)
                root.mainloop()
                
                file_counter += 1
            except Exception as e:
                print(f"Error processing file {file_path}: {str(e)}")
                file_counter += 1
                continue


if __name__ == '__main__':
    try:
        config = load_config()
        process_files_and_save(config)
    except Exception as e:
        print(f"Error: {str(e)}")