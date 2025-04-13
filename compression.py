#!/usr/bin/env python3
"""
PNG Image Compressor - A tool to reduce the file size of PNG images
with minimal quality loss using both CLI and GUI interfaces.
"""

import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
import time

# For GUI
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QListWidget,
    QMessageBox, QSpinBox, QGroupBox, QScrollArea, QStatusBar,
    QSplitter, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap, QFont, QDragEnterEvent, QDropEvent


class ImageCompressor:
    """Core functionality for image compression."""
    
    def __init__(self, optimization_level=6):
        self.optimization_level = optimization_level
    
    def compress_image(self, input_path, output_path=None, callback=None):
        """
        Compress a PNG image.
        
        Args:
            input_path: Path to the input image
            output_path: Path to save the compressed image (if None, overwrites original)
            callback: Optional callback function to report progress
            
        Returns:
            dict: Results containing original and new sizes, paths, etc.
        """
        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
                
            # Default output path is the same as input
            if output_path is None:
                output_dir = os.path.dirname(input_path)
                filename = os.path.basename(input_path)
                name, ext = os.path.splitext(filename)
                output_path = os.path.join(output_dir, f"{name}_compressed{ext}")
            
            if callback:
                callback({"status": "started", "input_path": input_path})
            
            # Get original file size
            original_size = os.path.getsize(input_path)
            
            # Open and optimize the image
            with Image.open(input_path) as img:
                # Ensure we're working with PNG format
                if img.format != "PNG":
                    img = img.convert("RGBA")
                
                # Create output directory if needed
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Save with optimization
                img.save(
                    output_path,
                    "PNG",
                    optimize=True,
                    quality=90,  # Quality for saving, 0-100
                    compress_level=self.optimization_level  # PNG compression level, 0-9
                )
            
            if callback:
                callback({"status": "processing", "input_path": input_path, "progress": 50})
            
            # Get new file size
            new_size = os.path.getsize(output_path)
            size_reduction = original_size - new_size
            if original_size > 0:
                percentage_saved = (size_reduction / original_size) * 100
            else:
                percentage_saved = 0
                
            result = {
                "input_path": input_path,
                "output_path": output_path,
                "original_size": original_size,
                "new_size": new_size,
                "bytes_saved": size_reduction,
                "percentage_saved": percentage_saved,
                "success": True
            }
            
            if callback:
                callback({"status": "completed", **result})
                
            return result
        
        except Exception as e:
            error_result = {
                "input_path": input_path,
                "output_path": output_path,
                "error": str(e),
                "success": False
            }
            if callback:
                callback({"status": "error", **error_result})
            return error_result

    def batch_compress(self, input_files, output_dir=None, max_workers=None, callback=None):
        """
        Compress multiple PNG images.
        
        Args:
            input_files: List of paths to input images
            output_dir: Directory to save compressed images (if None, saves alongside originals)
            max_workers: Maximum number of parallel compression tasks
            callback: Optional callback function to report progress
            
        Returns:
            list: Results for each processed image
        """
        results = []
        total_files = len(input_files)
        processed = 0
        
        if callback:
            callback({"status": "batch_started", "total": total_files})
        
        def process_callback(result):
            nonlocal processed
            processed += 1
            if callback:
                result["overall_progress"] = processed / total_files * 100
                callback(result)
            
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for input_path in input_files:
                if not input_path.lower().endswith('.png'):
                    result = {
                        "input_path": input_path,
                        "error": "Not a PNG file",
                        "success": False
                    }
                    results.append(result)
                    if callback:
                        process_callback({"status": "error", **result})
                    continue
                    
                if output_dir:
                    filename = os.path.basename(input_path)
                    name, ext = os.path.splitext(filename)
                    output_path = os.path.join(output_dir, f"{name}_compressed{ext}")
                else:
                    output_path = None
                
                future = executor.submit(
                    self.compress_image,
                    input_path,
                    output_path,
                    process_callback
                )
                futures.append(future)
            
            # Collect results
            for future in futures:
                result = future.result()
                results.append(result)
        
        if callback:
            callback({"status": "batch_completed", "results": results})
            
        return results


class CompressionWorker(QThread):
    """Worker thread for handling image compression without blocking the GUI."""
    
    progress_updated = pyqtSignal(dict)
    compression_finished = pyqtSignal(list)
    
    def __init__(self, input_files, output_dir=None, optimization_level=6):
        super().__init__()
        self.input_files = input_files
        self.output_dir = output_dir
        self.optimization_level = optimization_level
        self.compressor = ImageCompressor(optimization_level)
    
    def run(self):
        results = self.compressor.batch_compress(
            self.input_files,
            self.output_dir,
            callback=self.update_progress
        )
        self.compression_finished.emit(results)
    
    def update_progress(self, progress_data):
        self.progress_updated.emit(progress_data)


class FileListWidget(QListWidget):
    """Custom list widget that supports drag and drop for files."""
    
    files_dropped = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(200)
        self.setStyleSheet("""
            QListWidget {
                border: 2px dashed #aaa;
                border-radius: 5px;
                padding: 5px;
                background-color: #f9f9f9;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e0e0ff;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and path.lower().endswith('.png'):
                files.append(path)
        
        if files:
            self.files_dropped.emit(files)


class MainWindow(QMainWindow):
    """Main GUI window for the PNG compressor application."""
    
    def __init__(self):
        super().__init__()
        
        self.input_files = []
        self.output_directory = None
        self.compression_results = []
        self.current_worker = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("PNG Image Compressor")
        self.setGeometry(100, 100, 800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Header with title and description
        header = QVBoxLayout()
        title_label = QLabel("PNG Image Compressor")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        desc_label = QLabel("Reduce the size of your PNG images with minimal quality loss")
        header.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        header.addWidget(desc_label, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(header)
        
        # Main content area - using splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Input section
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        
        # File list with drag & drop support
        self.file_list = FileListWidget()
        self.file_list.files_dropped.connect(self.add_files)
        
        # Add instruction label
        drop_label = QLabel("Drag and drop PNG files here or use the buttons below")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_layout.addWidget(drop_label)
        input_layout.addWidget(self.file_list)
        
        # Buttons for file operations
        file_buttons_layout = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.clicked.connect(self.browse_files)
        self.clear_files_btn = QPushButton("Clear List")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons_layout.addWidget(self.add_files_btn)
        file_buttons_layout.addWidget(self.clear_files_btn)
        input_layout.addLayout(file_buttons_layout)
        
        # Settings group
        settings_group = QGroupBox("Compression Settings")
        settings_layout = QHBoxLayout(settings_group)
        
        # Optimization level
        opt_label = QLabel("Optimization Level:")
        self.opt_level = QSpinBox()
        self.opt_level.setRange(1, 9)
        self.opt_level.setValue(6)
        self.opt_level.setToolTip("Higher values = smaller files but slower compression (1-9)")
        
        # Output directory setting
        out_dir_label = QLabel("Output Directory:")
        self.out_dir_btn = QPushButton("Select Folder")
        self.out_dir_btn.clicked.connect(self.select_output_dir)
        self.out_dir_display = QLabel("Same as input files")
        self.out_dir_display.setStyleSheet("color: #666; font-style: italic;")
        
        opt_layout = QHBoxLayout()
        opt_layout.addWidget(opt_label)
        opt_layout.addWidget(self.opt_level)
        opt_layout.addStretch()
        
        out_layout = QHBoxLayout()
        out_layout.addWidget(out_dir_label)
        out_layout.addWidget(self.out_dir_btn)
        out_layout.addWidget(self.out_dir_display)
        out_layout.addStretch()
        
        settings_layout.addLayout(opt_layout)
        settings_layout.addLayout(out_layout)
        input_layout.addWidget(settings_group)
        
        # Compress button
        self.compress_btn = QPushButton("Compress Images")
        self.compress_btn.setEnabled(False)
        self.compress_btn.clicked.connect(self.start_compression)
        self.compress_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        input_layout.addWidget(self.compress_btn)
        
        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_layout.addWidget(self.progress_bar)
        
        splitter.addWidget(input_widget)
        
        # Results section
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        
        results_label = QLabel("Compression Results")
        results_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        results_layout.addWidget(results_label)
        
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        results_layout.addWidget(self.results_list)
        
        # Summary stats
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(summary_frame)
        
        self.total_saved_label = QLabel("Total Size Saved: 0 B")
        self.avg_reduction_label = QLabel("Average Reduction: 0%")
        
        summary_layout.addWidget(self.total_saved_label)
        summary_layout.addWidget(self.avg_reduction_label)
        
        results_layout.addWidget(summary_frame)
        
        splitter.addWidget(results_widget)
        
        # Set a nicer proportion for the splitter
        splitter.setSizes([400, 200])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        # Set central widget
        self.setCentralWidget(main_widget)
        
        # Apply stylesheet for the entire app
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 1ex;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 5px 15px;
                border-radius: 3px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)
    
    def browse_files(self):
        """Open file dialog to select PNG images."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PNG Images",
            "",
            "PNG Images (*.png)"
        )
        if files:
            self.add_files(files)
    
    def add_files(self, files):
        """Add files to the list."""
        for file_path in files:
            if file_path not in self.input_files and file_path.lower().endswith('.png'):
                self.input_files.append(file_path)
                self.file_list.addItem(os.path.basename(file_path))
        
        self.compress_btn.setEnabled(len(self.input_files) > 0)
    
    def clear_files(self):
        """Clear the file list."""
        self.input_files = []
        self.file_list.clear()
        self.compress_btn.setEnabled(False)
    
    def select_output_dir(self):
        """Select output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )
        if directory:
            self.output_directory = directory
            self.out_dir_display.setText(os.path.basename(directory))
            self.out_dir_display.setStyleSheet("color: #000; font-style: normal;")
        else:
            self.output_directory = None
            self.out_dir_display.setText("Same as input files")
            self.out_dir_display.setStyleSheet("color: #666; font-style: italic;")
    
    def start_compression(self):
        """Start the compression process."""
        if not self.input_files:
            return
            
        # Clear previous results
        self.results_list.clear()
        self.compression_results = []
        
        # Update UI state
        self.compress_btn.setEnabled(False)
        self.add_files_btn.setEnabled(False)
        self.clear_files_btn.setEnabled(False)
        self.out_dir_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # Create and start the worker thread
        self.current_worker = CompressionWorker(
            self.input_files,
            self.output_directory,
            self.opt_level.value()
        )
        self.current_worker.progress_updated.connect(self.update_progress)
        self.current_worker.compression_finished.connect(self.compression_completed)
        self.current_worker.start()
        
        self.statusBar.showMessage("Compressing images...")
    
    def update_progress(self, data):
        """Update the progress UI based on worker thread updates."""
        status = data.get("status")
        
        if status == "batch_started":
            self.progress_bar.setMaximum(100)
        
        elif status == "started":
            self.statusBar.showMessage(f"Processing: {os.path.basename(data.get('input_path', ''))}")
        
        elif status == "processing":
            # Individual file progress updates
            pass
        
        elif status == "completed":
            # Add to results list
            result = data
            if result.get("success"):
                original = self.format_size(result.get("original_size", 0))
                new = self.format_size(result.get("new_size", 0))
                saved = round(result.get("percentage_saved", 0), 1)
                
                item_text = f"{os.path.basename(result.get('input_path', ''))} - {original} → {new} ({saved}% saved)"
                self.results_list.addItem(item_text)
                self.compression_results.append(result)
                
                # Update overall progress if available
                if "overall_progress" in data:
                    self.progress_bar.setValue(int(data["overall_progress"]))
        
        elif status == "error":
            # Handle errors
            error_msg = f"Error processing {os.path.basename(data.get('input_path', ''))}: {data.get('error', 'Unknown error')}"
            self.results_list.addItem(error_msg)
            
            # Update overall progress if available
            if "overall_progress" in data:
                self.progress_bar.setValue(int(data["overall_progress"]))
                
        elif status == "batch_completed":
            # This is handled by compression_completed signal
            pass
    
    def compression_completed(self, results):
        """Handle completion of all compression tasks."""
        # Update UI state
        self.compress_btn.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.clear_files_btn.setEnabled(True)
        self.out_dir_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        
        # Calculate stats
        total_original = sum(r.get("original_size", 0) for r in results if r.get("success"))
        total_new = sum(r.get("new_size", 0) for r in results if r.get("success"))
        total_saved = total_original - total_new
        
        success_results = [r for r in results if r.get("success")]
        if success_results:
            avg_reduction = sum(r.get("percentage_saved", 0) for r in success_results) / len(success_results)
        else:
            avg_reduction = 0
        
        # Update summary
        self.total_saved_label.setText(f"Total Size Saved: {self.format_size(total_saved)}")
        self.avg_reduction_label.setText(f"Average Reduction: {round(avg_reduction, 1)}%")
        
        # Update status
        self.statusBar.showMessage(f"Compression completed - {len(success_results)} of {len(results)} files processed successfully")
        
        # Show a completion dialog
        if success_results:
            msg = QMessageBox()
            msg.setWindowTitle("Compression Complete")
            msg.setText(f"Successfully compressed {len(success_results)} images")
            msg.setInformativeText(f"Total size reduction: {self.format_size(total_saved)} ({round(avg_reduction, 1)}% average)")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
    
    @staticmethod
    def format_size(size_bytes):
        """Format byte size to human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"


def cli_main():
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(description="Compress PNG images to reduce file size.")
    parser.add_argument("input", nargs='+', help="Input PNG file(s) or directory containing PNG files")
    parser.add_argument("-o", "--output", help="Output directory for compressed images")
    parser.add_argument("-l", "--level", type=int, default=6, choices=range(1, 10),
                        help="Optimization level (1-9, higher means more compression but slower)")
    parser.add_argument("-r", "--recursive", action="store_true", 
                        help="Recursively process directories")
    
    args = parser.parse_args()
    
    # Process input paths
    input_files = []
    for path in args.input:
        if os.path.isfile(path) and path.lower().endswith('.png'):
            input_files.append(path)
        elif os.path.isdir(path):
            if args.recursive:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith('.png'):
                            input_files.append(os.path.join(root, file))
            else:
                for file in os.listdir(path):
                    file_path = os.path.join(path, file)
                    if os.path.isfile(file_path) and file.lower().endswith('.png'):
                        input_files.append(file_path)
    
    if not input_files:
        print("No PNG files found!")
        return
    
    print(f"Found {len(input_files)} PNG files to process")
    
    # Create compressor
    compressor = ImageCompressor(optimization_level=args.level)
    
    # Define callback for progress updates
    def progress_callback(data):
        status = data.get("status")
        if status == "started":
            print(f"Processing: {os.path.basename(data.get('input_path', ''))}")
        elif status == "completed":
            original = data.get("original_size", 0)
            new = data.get("new_size", 0)
            saved = round(data.get("percentage_saved", 0), 1)
            print(f"Compressed: {os.path.basename(data.get('input_path', ''))} - "
                  f"{original} → {new} bytes ({saved}% saved)")
        elif status == "error":
            print(f"Error: {data.get('error', 'Unknown error')} - {os.path.basename(data.get('input_path', ''))}")
    
    # Compress images
    results = compressor.batch_compress(
        input_files,
        args.output,
        callback=progress_callback
    )
    
    # Print summary
    successful = [r for r in results if r.get("success")]
    total_original = sum(r.get("original_size", 0) for r in successful)
    total_new = sum(r.get("new_size", 0) for r in successful)
    total_saved = total_original - total_new
    
    if successful:
        avg_reduction = sum(r.get("percentage_saved", 0) for r in successful) / len(successful)
    else:
        avg_reduction = 0
    
    print("\nCompression Summary:")
    print(f"Files processed successfully: {len(successful)}/{len(results)}")
    print(f"Total size reduction: {total_saved} bytes ({round(avg_reduction, 1)}% average)")


def gui_main():
    """Graphical user interface entry point."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # If arguments are provided, use CLI mode; otherwise, launch GUI
    if len(sys.argv) > 1:
        cli_main()
    else:
        gui_main()