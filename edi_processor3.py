import os
import json
import glob
from datetime import datetime, timedelta
import re

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
        if value == '0' or value == 0 or value == '00' or value == '000':
            raise ValueError(f"Error: '{field}' cannot be 0, 00, or 000!")

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

def select_po1_segments(po1_segments):
    """Display PO1 segments with checkboxes and prompt for selection."""
    if not po1_segments:
        return []

    print("\nListing PO1 segments with checkboxes (select by sequence numbers):")
    for i, segment in enumerate(po1_segments, 1):
        print(f"[ ] PO_sequence {i}: {segment}")

    print("\nSelect PO1 segments by entering sequence numbers (e.g., '1,3,5'). Press Enter to select none:")
    while True:
        user_input = input("Sequence numbers: ").strip()
        if user_input == "":
            print("No segments selected for updating.")
            return []

        try:
            selected_indices = [int(x.strip()) for x in user_input.split(',')]
            if not all(1 <= x <= len(po1_segments) for x in selected_indices):
                print(f"Invalid sequence numbers. Enter numbers between 1 and {len(po1_segments)}.")
                continue
            if len(set(selected_indices)) != len(selected_indices):
                print("Duplicate sequence numbers detected. Enter unique numbers.")
                continue
            selected_segments = [(i, po1_segments[i-1]) for i in selected_indices]
            print("\nSelected PO1 segments:")
            for seq_num, segment in selected_segments:
                print(f"[✓] PO_sequence {seq_num}: {segment}")
            return selected_segments
        except ValueError:
            print("Invalid input. Enter comma-separated numbers (e.g., '1,3,5').")

def get_user_input_for_po1_elements(selected_po1_segments):
    """Prompt user to edit specific elements in selected PO1 segments."""
    element_indices = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
    new_elements_list = []

    for seq_num, po1_line in selected_po1_segments:
        parts = po1_line.split('*')
        print(f"\nEditing PO1 Segment (Sequence {seq_num}): {po1_line}")
        new_elements = {}

        for idx in element_indices:
            if idx < len(parts):
                current_value = parts[idx]
                element_name = "Quantity" if idx == 2 else f"Element {idx}"
                print(f"[ ] {element_name}: {current_value}")
                user_input = input(f"Enter new value for {element_name} (press Enter to keep '{current_value}'): ").strip()

                if user_input:
                    if idx == 2:
                        try:
                            qty = int(user_input)
                            if not (0 <= qty <= 10):
                                print(f"Warning: Quantity must be between 0 and 10. Keeping original: {current_value}")
                                new_elements[idx] = None
                                print(f"[✓] {element_name}: {current_value}")
                            else:
                                print(f"New quantity set: {qty}")
                                new_elements[idx] = str(qty)
                                print(f"[✓] {element_name}: {qty}")
                        except ValueError:
                            print(f"Warning: Invalid quantity '{user_input}'. Keeping original: {current_value}")
                            new_elements[idx] = None
                            print(f"[✓] {element_name}: {current_value}")
                    else:
                        print(f"New value set: {user_input}")
                        new_elements[idx] = user_input
                        print(f"[✓] {element_name}: {user_input}")
                else:
                    print(f"Keeping original value: {current_value}")
                    new_elements[idx] = None
                    print(f"[✓] {element_name}: {current_value}")
            else:
                print(f"Warning: Element {idx} not found in PO1 segment (Sequence {seq_num}). Skipping.")
                new_elements[idx] = None
                print(f"[✓] Element {idx}: (not present)")

        print(f"[✓] PO1 Segment (Sequence {seq_num}) editing completed.")
        new_elements_list.append((seq_num, new_elements))

    return new_elements_list

def modify_edi_file(content, config, selected_segments=None, new_elements_list=None, is_bulk_processing=False, file_counter=None):
    selected_segments = selected_segments or []
    new_elements_list = new_elements_list or []
    
    is_single_line = '\n' not in content and '*' in content
    if is_single_line:
        print("Detected single-line EDI file. Splitting into segments...")
        lines = [line.strip().rstrip('~') for line in content.split('~') if line.strip()]
    else:
        lines = [line.strip().rstrip('~') for line in content.strip().split('\n') if line.strip()]

    po1_groups = []
    current_group = []
    po1_index = 0
    related_segments = ['CTP*', 'PID*', 'PO4*', 'SDQ*', 'AMT*']

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

    selected_seq_nums = [seq_num for seq_num, _ in selected_segments]
    new_elements_dict = {seq_num: elements for seq_num, elements in new_elements_list}
    filtered_lines = []
    po1_counter = 0

    for index, group in po1_groups:
        if group[0].startswith('PO1*'):
            # Only include selected PO1 segments if any were selected
            if selected_segments and index not in selected_seq_nums:
                print(f"Skipping unselected PO1 segment (sequence {index})")
                continue
            po1_counter += 1
            po1_line = group[0]
            parts = po1_line.split('*')
            print(f"Keeping original sequence number {parts[1]} for PO1 segment (original sequence {index})")
            # Apply changes to selected PO1 segments
            if index in selected_seq_nums and index in new_elements_dict:
                for idx, value in new_elements_dict[index].items():
                    if value is not None:
                        parts[idx] = value
                        print(f"Applying user element for PO1 at position {idx}: {value}")
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
            # Process non-PO1 segments
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
                    print(f"Updating SE Segment Count: {segment_count}")
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

def process_files_and_save(config):
    input_folder = config.get('input_folder_path')
    output_folder = config.get('output_folder_path')

    if not input_folder or not os.path.exists(input_folder):
        raise FileNotFoundError(f"Input folder '{input_folder}' not found!")
    if not output_folder:
        raise ValueError("Output folder path is missing in the configuration!")

    os.makedirs(output_folder, exist_ok=True)

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

                is_single_line = '\n' not in content and '*' in content
                if is_single_line:
                    lines = [line.strip().rstrip('~') for line in content.split('~') if line.strip()]
                else:
                    lines = [line.strip().rstrip('~') for line in content.strip().split('\n') if line.strip()]

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

                selected_segments = []
                new_elements_list = []

                # For bulk processing, allow PO1 selection
                if is_bulk_processing:
                    po1_only_segments = [line for line in lines if line.startswith('PO1*')]
                    print(f"Found {len(po1_only_segments)} PO1 segments in the file.")
                    selected_segments = select_po1_segments(po1_only_segments)
                    if selected_segments:
                        new_elements_list = get_user_input_for_po1_elements(selected_segments)
                # For single file, skip PO1 processing
                else:
                    print("Single file detected, skipping PO1 segment updates.")

                updated_content = modify_edi_file(
                    content,
                    config,
                    selected_segments=selected_segments,
                    new_elements_list=new_elements_list,
                    is_bulk_processing=is_bulk_processing,
                    file_counter=file_counter if is_bulk_processing else None
                )

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                base_filename, file_extension = os.path.splitext(os.path.basename(file_path))
                new_filename = f"processed_{base_filename}_{timestamp}{file_extension}"
                output_file_path = os.path.join(output_folder, new_filename)

                # Always save the output file, even if no changes were made
                with open(output_file_path, 'w', encoding='utf-8') as output_file:
                    output_file.write(updated_content)
                print(f"Processed & saved: {output_file_path}")
                if content == updated_content:
                    print(f"No changes made to: {os.path.basename(file_path)}")

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