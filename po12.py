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
        if value == '0' or value == 0:
            raise ValueError(f"Error: '{field}' cannot be 0!")
        
    for field in fields_to_check:
        value = config[field]
        if value == '00' or value == 0:
            raise ValueError(f"Error: '{field}' cannot be 00!")
        
    for field in fields_to_check:
        value = config[field]
        if value == '000' or value == 0:
            raise ValueError(f"Error: '{field}' cannot be 000!")

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

def get_user_input_for_po1_elements(po1_segments):
    """Prompt user for specific elements in each PO1 segment, with checkboxes for elements and segments."""
    element_indices = [2, 6, 7, 8, 9, 10, 11, 12, 13]  # Indices for 48, UP, 070501064863, VA, 64863, CB, 0862021, BO, 000
    new_elements_list = []

    for i, po1_line in enumerate(po1_segments, 1):
        parts = po1_line.split('*')
        print(f"\n[ ] PO1 Segment {i}: {po1_line}")
        new_elements = {}

        for idx in element_indices:
            if idx < len(parts):
                current_value = parts[idx]
                element_name = "Quantity" if idx == 2 else f"Element {idx}"
                print(f"[ ] {element_name}: {current_value}")
                user_input = input(f"Enter new value for {element_name} (current: {current_value}): ").strip()

                if user_input:
                    if idx == 2:  # Validate quantity (index 2)
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
                    else:  # Other elements accept any non-empty input
                        print(f"New value set: {user_input}")
                        new_elements[idx] = user_input
                        print(f"[✓] {element_name}: {user_input}")
                else:
                    print(f"Keeping original value: {current_value}")
                    new_elements[idx] = None
                    print(f"[✓] {element_name}: {current_value}")
            else:
                print(f"Warning: Element {idx} not found in PO1 segment {i}. Skipping.")
                new_elements[idx] = None
                print(f"[✓] Element {idx}: (not present)")

        print(f"[✓] PO1 Segment {i} completed.")
        new_elements_list.append(new_elements)

    return new_elements_list

def switch_po1_segments(po1_segments, new_elements_list):
    """Prompt user to switch the order of PO1 segments."""
    if len(po1_segments) <= 1:
        print("Only one or no PO1 segments found. No switching needed.")
        return po1_segments, new_elements_list

    print("\nCurrent PO1 segment order:")
    for i, segment in enumerate(po1_segments, 1):
        print(f"Position {i}: {segment}")

    print(f"\nEnter new positions for each PO1 segment (1 to {len(po1_segments)}). Press Enter to keep current order.")
    new_order = []
    for i in range(1, len(po1_segments) + 1):
        while True:
            user_input = input(f"New position for PO1 Segment {i} (current position: {i}): ").strip()
            if user_input == "":
                new_order = list(range(1, len(po1_segments) + 1))  # Keep original order
                print("Keeping original PO1 segment order.")
                return po1_segments, new_elements_list
            try:
                pos = int(user_input)
                if 1 <= pos <= len(po1_segments) and pos not in new_order:
                    new_order.append(pos)
                    break
                else:
                    print(f"Invalid position. Enter a unique number between 1 and {len(po1_segments)}.")
            except ValueError:
                print("Invalid input. Enter a number or press Enter to keep order.")

    # Validate that all positions are covered
    if sorted(new_order) != list(range(1, len(po1_segments) + 1)):
        print("Error: Not all positions were specified correctly. Keeping original order.")
        return po1_segments, new_elements_list

    # Reorder segments and element updates
    reordered_segments = [None] * len(po1_segments)
    reordered_elements = [None] * len(new_elements_list)
    for old_pos, new_pos in enumerate(new_order, 1):
        reordered_segments[new_pos - 1] = po1_segments[old_pos - 1]
        reordered_elements[new_pos - 1] = new_elements_list[old_pos - 1]

    print("\nNew PO1 segment order:")
    for i, segment in enumerate(reordered_segments, 1):
        print(f"Position {i}: {segment}")

    return reordered_segments, reordered_elements

def modify_edi_file(content, config, is_bulk_processing=False, file_counter=None):
    is_single_line = '\n' not in content and '*' in content
    if is_single_line:
        print("Detected single-line EDI file. Splitting into segments...")
        lines = [line.strip().rstrip('~') for line in content.split('~') if line.strip()]
    else:
        lines = [line.strip().rstrip('~') for line in content.strip().split('\n') if line.strip()]

    # Print PO1 segments with sequence numbers
    print("\nListing PO1 segments with sequence numbers:")
    po1_sequence = 1
    for line in lines:
        list_of_strings = line.split("*")
        if list_of_strings[0] == 'PO1':
            print(f"PO_sequence {po1_sequence}    :  {line}")
            po1_sequence += 1

    # Find PO1 segments and prompt for element updates
    po1_segments = [line for line in lines if line.startswith('PO1*')]
    po1_count = len(po1_segments)
    print(f"\nFound {po1_count} PO1 segments in the file.")

    if po1_count > 0:
        print("\nPrompting for PO1 element updates...")
        new_elements_list = get_user_input_for_po1_elements(po1_segments)
        # Prompt for switching PO1 segments
        po1_segments, new_elements_list = switch_po1_segments(po1_segments, new_elements_list)
    else:
        new_elements_list = []

    original_ctt_value = None
    for line in lines:
        if line.startswith('CTT*'):
            parts = line.split('*')
            if len(parts) > 1:
                original_ctt_value = parts[1]
                print(f"Original CTT count found: {original_ctt_value}")
                break

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

    # Use config quantities only if specified, otherwise use user inputs
    first_qty = config.get("First_PO1_Quantity")
    second_qty = config.get("Second_PO1_Quantity")

    for line in body_lines:
        if line.startswith('PO1*'):
            po1_index += 1
            # Use the reordered PO1 segment
            parts = po1_segments[po1_index - 1].split('*')
            
            # Assign serial number to PO1 segment
            parts[1] = str(po1_index)
            print(f"Assigned serial number {po1_index} to PO1 segment {po1_index}")
            
            # Apply config quantities for first two if specified
            if po1_index == 1 and first_qty is not None and str(first_qty).strip() != "":
                print(f"Using config First_PO1_Quantity: {first_qty}")
                parts[2] = str(first_qty)
            elif po1_index == 2 and second_qty is not None and str(second_qty).strip() != "":
                print(f"Using config Second_PO1_Quantity: {second_qty}")
                parts[2] = str(second_qty)
            elif po1_index <= po1_count and new_elements_list:
                # Apply user-provided elements
                user_elements = new_elements_list[po1_index - 1]
                for idx, value in user_elements.items():
                    if value is not None:  # Only update if user provided a value
                        parts[idx] = value
                        print(f"Applying user element for PO1 {po1_index} at position {idx}: {value}")
            
            filtered_body.append('*'.join(parts))
        else:
            filtered_body.append(line)

    lines = filtered_body + footer_lines

    for i, line in enumerate(lines):
        parts = line.split('*')

        if line.startswith('ISA*') and len(parts) > 8:
            sender_id = config.get('ISA_Sender_ID', '').strip() or parts[6]
            receiver_id = config.get('ISA_Receiver_ID', '').strip() or parts[8]
            parts[6] = pad_isa_field(sender_id)
            parts[8] = pad_isa_field(receiver_id)
            lines[i] = '*'.join(parts)

        elif line.startswith('GS*') and len(parts) > 3:
            parts[2] = config.get('GS_Sender_ID', '').strip() or parts[2]
            parts[3] = config.get('GS_Receiver_ID', '').strip() or parts[3]
            lines[i] = '*'.join(parts)

        elif line.startswith('DTM*') and len(parts) > 2:
            parts[2] = adjust_date(parts[2], config, "DTM")
            lines[i] = '*'.join(parts)

        elif line.startswith('G62*') and len(parts) > 2:
            parts[2] = adjust_date(parts[2], config, "G62")
            lines[i] = '*'.join(parts)

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
            lines[i] = '*'.join(parts) 

        elif line.startswith('CTT*'):
            final_po1_count = sum(1 for line in filtered_body if line.startswith('PO1*'))
            if ctt_original:
                parts = ctt_original.split('*')
                parts[1] = str(final_po1_count)
                lines[i] = '*'.join(parts)
            else:
                lines[i] = f"CTT*{final_po1_count}"
            print(f"Updating CTT count to: {final_po1_count}")

        elif line.startswith('SE*') and len(parts) > 1:
            segment_count = len(lines) - 4
            print(f"Updating SE Segment Count: {parts[1]} → {segment_count}")
            parts[1] = str(segment_count)
            lines[i] = '*'.join(parts)

    if is_single_line:
        return '~'.join(lines) + '~'
    else:
        return '\n'.join(line + '~' for line in lines)

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
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            updated_content = modify_edi_file(
                content, 
                config, 
                is_bulk_processing=is_bulk_processing,
                file_counter=file_counter if is_bulk_processing else None
            )
            

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_filename, file_extension = os.path.splitext(os.path.basename(file_path))
            print(f"Base filename: {base_filename}, Extension: {file_extension}")

            new_filename = f"{base_filename}_{timestamp}{file_extension}"
            print(f"New filename with timestamp: {new_filename}")

            output_file_path = os.path.join(output_folder, new_filename)
            print(f"Output file path: {output_file_path}")

            if content != updated_content:
                with open(output_file_path, 'w', encoding='utf-8') as output_file:
                    output_file.write(updated_content)
                print(f"Processed & saved: {output_file_path}")
            else:
                print(f"No changes needed: {os.path.basename(file_path)}")

            file_counter += 1

if __name__ == '__main__':
    try:
        config = load_config()
        process_files_and_save(config)
    except Exception as e:
        print(f"Error: {str(e)}")