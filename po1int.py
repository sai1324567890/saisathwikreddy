import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import os
import json

class EDIProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("EDI File Processor")
        self.root.geometry("1400x900")

        # Style configuration
        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=30)
        style.configure("Custom.TButton", padding=5)

        # Variables
        self.file_path = None
        self.po1_segments = []
        self.selected_segments = set()
        self.edited_values = {}
        self.original_content = None

        # Main container with padding
        main_container = ttk.Frame(root, padding="20")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Header
        header_frame = ttk.Frame(main_container)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        ttk.Label(header_frame, text="EDI File Processor", font=("Helvetica", 24)).pack()
        ttk.Label(header_frame, text="Select PO1 segments and edit their elements", font=("Helvetica", 12)).pack()

        # File selection with improved styling
        file_frame = ttk.LabelFrame(main_container, text="File Selection", padding="10")
        file_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        
        self.file_label = ttk.Label(file_frame, text="No file selected", font=("Helvetica", 10))
        self.file_label.grid(row=0, column=0, padx=10)
        
        select_file_btn = ttk.Button(file_frame, text="Select EDI File", command=self.load_file, style="Custom.TButton")
        select_file_btn.grid(row=0, column=1, padx=10)

        # PO1 Segments Display with improved styling
        segments_frame = ttk.LabelFrame(main_container, text="PO1 Segments", padding="10")
        segments_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        segments_frame.columnconfigure(0, weight=1)
        segments_frame.rowconfigure(0, weight=1)

        # Enhanced Treeview
        columns = ("checkbox", "sequence", "quantity", "unit", "price", "product_id", "vendor_id", 
                  "product_code", "contract_number", "buyer_code")
        self.tree = ttk.Treeview(segments_frame, columns=columns, style="Custom.Treeview")
        
        # Configure columns
        self.tree.heading("checkbox", text="Select")
        self.tree.heading("sequence", text="Seq")
        self.tree.heading("quantity", text="Quantity")
        self.tree.heading("unit", text="Unit")
        self.tree.heading("price", text="Price")
        self.tree.heading("product_id", text="Product ID")
        self.tree.heading("vendor_id", text="Vendor ID")
        self.tree.heading("product_code", text="Product Code")
        self.tree.heading("contract_number", text="Contract #")
        self.tree.heading("buyer_code", text="Buyer Code")
        
        # Column widths
        self.tree.column("checkbox", width=60, anchor="center")
        self.tree.column("sequence", width=60, anchor="center")
        self.tree.column("quantity", width=80, anchor="center")
        self.tree.column("unit", width=70, anchor="center")
        self.tree.column("price", width=80, anchor="center")
        self.tree.column("product_id", width=120, anchor="center")
        self.tree.column("vendor_id", width=100, anchor="center")
        self.tree.column("product_code", width=120, anchor="center")
        self.tree.column("contract_number", width=100, anchor="center")
        self.tree.column("buyer_code", width=100, anchor="center")

        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Enhanced scrollbar
        scrollbar = ttk.Scrollbar(segments_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Editing Frame with improved layout
        edit_frame = ttk.LabelFrame(main_container, text="Edit Selected Segment", padding="10")
        edit_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        edit_frame.columnconfigure(1, weight=1)
        edit_frame.columnconfigure(3, weight=1)
        edit_frame.columnconfigure(5, weight=1)

        # Edit fields with better organization
        self.create_edit_field(edit_frame, "Quantity:", 0, 0, "quantity_var")
        self.create_edit_field(edit_frame, "Unit:", 0, 2, "unit_var")
        self.create_edit_field(edit_frame, "Price:", 0, 4, "price_var")
        self.create_edit_field(edit_frame, "Product ID:", 1, 0, "product_id_var")
        self.create_edit_field(edit_frame, "Vendor ID:", 1, 2, "vendor_id_var")
        self.create_edit_field(edit_frame, "Product Code:", 2, 0, "product_code_var")
        self.create_edit_field(edit_frame, "Contract Number:", 2, 2, "contract_number_var")
        self.create_edit_field(edit_frame, "Buyer Code:", 2, 4, "buyer_code_var")

        # Action Buttons with improved styling
        button_frame = ttk.Frame(main_container)
        button_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)
        button_frame.columnconfigure(3, weight=1)

        ttk.Button(button_frame, text="Save Changes", command=self.save_changes, style="Custom.TButton").grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Move Up", command=self.move_up, style="Custom.TButton").grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Move Down", command=self.move_down, style="Custom.TButton").grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="Process File", command=self.process_file, style="Custom.TButton").grid(row=0, column=3, padx=5)

        # Status bar
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(main_container, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # Bind events
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<Button-1>', self.on_click)
        
        # Initialize status
        self.status_var.set("Ready")

    def create_edit_field(self, parent, label, row, col, var_name):
        ttk.Label(parent, text=label).grid(row=row, column=col, padx=5, pady=5, sticky=tk.E)
        var = tk.StringVar()
        setattr(self, var_name, var)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=col+1, padx=5, pady=5, sticky=(tk.W, tk.E))
        return entry

    def load_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("EDI Files", "*.edi"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.file_path = file_path
            self.file_label.config(text=os.path.basename(file_path))
            self.load_po1_segments()

    def load_po1_segments(self):
        try:
            with open(self.file_path, 'r') as file:
                self.original_content = file.read()
                
            self.tree.delete(*self.tree.get_children())
            self.po1_segments = []
            self.selected_segments.clear()
            self.edited_values.clear()
            
            lines = self.original_content.split('\n') if '\n' in self.original_content else self.original_content.split('~')
            lines = [line.strip().rstrip('~') for line in lines if line.strip()]
            
            seq = 1
            for line in lines:
                if line.startswith('PO1*'):
                    parts = line.split('*')
                    segment_data = {
                        'sequence': seq,
                        'content': line,
                        'quantity': parts[2] if len(parts) > 2 else '',
                        'unit': parts[4] if len(parts) > 4 else '',
                        'price': parts[5] if len(parts) > 5 else '',
                        'product_id': parts[7] if len(parts) > 7 else '',
                        'vendor_id': parts[9] if len(parts) > 9 else '',
                        'product_code': parts[11] if len(parts) > 11 else '',
                        'contract_number': parts[13] if len(parts) > 13 else '',
                        'buyer_code': parts[15] if len(parts) > 15 else ''
                    }
                    self.po1_segments.append(segment_data)
                    
                    self.tree.insert('', 'end', values=(
                        '☐', seq,
                        segment_data['quantity'],
                        segment_data['unit'],
                        segment_data['price'],
                        segment_data['product_id'],
                        segment_data['vendor_id'],
                        segment_data['product_code'],
                        segment_data['contract_number'],
                        segment_data['buyer_code']
                    ))
                    seq += 1
            
            self.status_var.set(f"Loaded {len(self.po1_segments)} PO1 segments")
            messagebox.showinfo("Success", f"Found {len(self.po1_segments)} PO1 segments")
        except Exception as e:
            self.status_var.set("Error loading file")
            messagebox.showerror("Error", f"Error loading file: {str(e)}")

    def on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":  # Checkbox column
                item = self.tree.identify_row(event.y)
                if item:
                    current_values = list(self.tree.item(item)['values'])
                    if current_values:
                        new_checkbox = '☑' if current_values[0] == '☐' else '☐'
                        current_values[0] = new_checkbox
                        self.tree.item(item, values=current_values)
                        
                        seq = current_values[1]
                        if new_checkbox == '☑':
                            self.selected_segments.add(seq)
                            self.status_var.set(f"Selected segment {seq}")
                        else:
                            self.selected_segments.discard(seq)
                            self.status_var.set(f"Deselected segment {seq}")

    def on_select(self, event):
        selected_items = self.tree.selection()
        if selected_items:
            item = selected_items[0]
            values = self.tree.item(item)['values']
            if values:
                self.quantity_var.set(values[2])
                self.unit_var.set(values[3])
                self.price_var.set(values[4])
                self.product_id_var.set(values[5])
                self.vendor_id_var.set(values[6])
                self.product_code_var.set(values[7])
                self.contract_number_var.set(values[8])
                self.buyer_code_var.set(values[9])
                self.status_var.set(f"Editing segment {values[1]}")

    def save_changes(self):
        selected_items = self.tree.selection()
        if not selected_items:
            self.status_var.set("No segment selected")
            messagebox.showwarning("Warning", "Please select a segment to edit")
            return

        item = selected_items[0]
        values = list(self.tree.item(item)['values'])
        
        # Update values
        values[2] = self.quantity_var.get()
        values[3] = self.unit_var.get()
        values[4] = self.price_var.get()
        values[5] = self.product_id_var.get()
        values[6] = self.vendor_id_var.get()
        values[7] = self.product_code_var.get()
        values[8] = self.contract_number_var.get()
        values[9] = self.buyer_code_var.get()
        
        self.tree.item(item, values=values)
        
        sequence = values[1]
        self.edited_values[sequence] = {
            'quantity': values[2],
            'unit': values[3],
            'price': values[4],
            'product_id': values[5],
            'vendor_id': values[6],
            'product_code': values[7],
            'contract_number': values[8],
            'buyer_code': values[9]
        }
        
        self.status_var.set(f"Saved changes to segment {sequence}")
        messagebox.showinfo("Success", "Changes saved")

    def move_up(self):
        selected_items = self.tree.selection()
        if not selected_items:
            self.status_var.set("No segment selected")
            return
            
        item = selected_items[0]
        prev_item = self.tree.prev(item)
        if prev_item:
            values = self.tree.item(item)['values']
            prev_values = self.tree.item(prev_item)['values']
            
            self.tree.item(item, values=prev_values)
            self.tree.item(prev_item, values=values)
            self.tree.selection_set(prev_item)
            self.status_var.set(f"Moved segment {values[1]} up")

    def move_down(self):
        selected_items = self.tree.selection()
        if not selected_items:
            self.status_var.set("No segment selected")
            return
            
        item = selected_items[0]
        next_item = self.tree.next(item)
        if next_item:
            values = self.tree.item(item)['values']
            next_values = self.tree.item(next_item)['values']
            
            self.tree.item(item, values=next_values)
            self.tree.item(next_item, values=values)
            self.tree.selection_set(next_item)
            self.status_var.set(f"Moved segment {values[1]} down")

    def process_file(self):
        if not self.file_path:
            self.status_var.set("No file loaded")
            messagebox.showerror("Error", "No file loaded")
            return

        try:
            is_single_line = '\n' not in self.original_content
            lines = self.original_content.split('~') if is_single_line else self.original_content.split('\n')
            lines = [line.strip().rstrip('~') for line in lines if line.strip()]

            processed_lines = []
            po1_count = 0

            for line in lines:
                if line.startswith('PO1*'):
                    po1_count += 1
                    if po1_count in self.edited_values:
                        parts = line.split('*')
                        edited = self.edited_values[po1_count]
                        parts[2] = edited['quantity']
                        parts[4] = edited['unit']
                        parts[5] = edited['price']
                        parts[7] = edited['product_id']
                        parts[9] = edited['vendor_id']
                        parts[11] = edited['product_code']
                        parts[13] = edited['contract_number']
                        parts[15] = edited['buyer_code']
                        line = '*'.join(parts)
                
                processed_lines.append(line)

            # Update CTT count if present
            for i, line in enumerate(processed_lines):
                if line.startswith('CTT*'):
                    parts = line.split('*')
                    parts[1] = str(po1_count)
                    processed_lines[i] = '*'.join(parts)

            # Create output content
            output_content = '~'.join(processed_lines) + '~' if is_single_line else '\n'.join(line + '~' for line in processed_lines)

            # Save to new file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = os.path.splitext(self.file_path)[0]
            output_path = f"{base_name}_processed_{timestamp}.edi"
            
            with open(output_path, 'w') as file:
                file.write(output_content)
            
            self.status_var.set(f"File processed and saved: {os.path.basename(output_path)}")
            messagebox.showinfo("Success", f"File processed and saved as:\n{os.path.basename(output_path)}")
            
        except Exception as e:
            self.status_var.set("Error processing file")
            messagebox.showerror("Error", f"Error processing file: {str(e)}")

if __name__ == '__main__':
    root = tk.Tk()
    app = EDIProcessor(root)
    root.mainloop()