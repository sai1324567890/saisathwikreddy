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
    
    
    # Only process days if configuration exists and is not empty
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

def modify_edi_file(content, config, is_bulk_processing=False, file_counter=None):
    is_single_line = '\n' not in content and '*' in content
    if is_single_line:
        print("Detected single-line EDI file. Splitting into segments...")
        lines = [line.strip() for line in content.split('~') if line.strip()]
    else:
        lines = content.strip().split('\n')

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
    po1_count = 0
    skip_mode = False

    first_qty = config.get("First_PO1_Quantity")
    second_qty = config.get("Second_PO1_Quantity")

    for line in body_lines:
        if line.startswith('PO1*'):
            po1_count += 1
            parts = line.split('*')
            
            if po1_count == 1:
                if first_qty is not None and first_qty.strip() != "":
                    print(f"Replacing first PO1 qty: {parts[1]} → {first_qty}")
                    parts[2] = str(first_qty)
                else:
                    print(f"Keeping original first PO1 qty: {parts[1]}")
            
            elif po1_count == 2:
                if second_qty is not None and second_qty.strip() != "":
                    print(f"Replacing second PO1 qty: {parts[1]} → {second_qty}")
                    parts[2] = str(second_qty)
                else:
                    print(f"Keeping original second PO1 qty: {parts[1]}")
            
            if po1_count <= 2:
                filtered_body.append('*'.join(parts))
                skip_mode = False
            else:
                skip_mode = True
        else:
            if not skip_mode:
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
            original_date_str = parts[2].strip().rstrip('~')
            
            if 'days_sign' in config and 'days_number' in config:
                if original_date_str and re.match(r'^\d{8}$', original_date_str):
                    try:
                        adjustment = config['days_number'] if config['days_sign'] == '+' else -config['days_number']
                        original_date = datetime.strptime(original_date_str, '%Y%m%d')
                        adjusted_date = original_date + timedelta(days=adjustment)
                        new_date = adjusted_date.strftime('%Y%m%d')
                        print(f"Updating DTM Date: {original_date_str} → {new_date} (Adjusted by {config['days_sign']}{config['days_number']} days)")
                        parts[2] = new_date
                    except ValueError:
                        print(f"Warning: Invalid DTM date '{original_date_str}' skipped")
                else:
                    print(f"Warning: DTM date '{original_date_str}' is not a valid 8-digit date, skipping adjustment")
            else:
                print(f"Keeping original DTM date: {original_date_str} (no day adjustment specified)")
            lines[i] = '*'.join(parts)

        elif line.startswith('BEG*') and len(parts) > 3:
            config_po_number = config.get('po_number', '').strip()
            
            if config_po_number:  # If PO number is provided in config
                if is_bulk_processing:  # For bulk processing
                    beg_identifier = f"{config_po_number}T{file_counter}"
                else:  # For single file processing
                    beg_identifier = config_po_number
            else:  # If no PO number in config, keep original
                beg_identifier = parts[3]
                # Remove 'T1' if it exists in the original PO number
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

    return '~'.join(lines) + '~' if is_single_line else '\n'.join(lines)

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
            print(f"Processing file: {os.path.basename(file_path)}")
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