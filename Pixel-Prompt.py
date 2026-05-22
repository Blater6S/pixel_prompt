
import io
import json
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# === COLOR THEME CONSTANTS ===
COLOR_BG = "#0F172A"            # Deep slate background
COLOR_CARD = "#1E293B"          # Slate card/input background
COLOR_TEXT_PRIMARY = "#F8FAFC"  # High-contrast text
COLOR_TEXT_MUTED = "#94A3B8"    # Medium-contrast text
COLOR_ACCENT = "#6366F1"        # Indigo primary accent
COLOR_ACCENT_HOVER = "#4F46E5"  # Active Indigo accent
COLOR_BORDER = "#334155"        # Slate border
COLOR_SUCCESS = "#10B981"       # Emerald accent


class DatabaseManager:
    """Manages SQLite database connections and operations for the PixelPrompt vault."""

    def __init__(self, db_path: str = "vault_V4.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the database schema if it doesn't already exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS person (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT,
                    image BLOB
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def save_record(self, description: str, image_bytes: bytes | None) -> None:
        """Inserts a new prompt record into the database."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO person (description, image) VALUES (?, ?)",
                (description, image_bytes),
            )
            conn.commit()
        finally:
            conn.close()

    def search_records(self, query: str) -> list[tuple[int, str, bytes | None]]:
        """Queries database for records containing query, sorted by ID in descending order."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, description, image FROM person WHERE description LIKE ? ORDER BY id DESC",
                (f"%{query}%",),
            )
            return cursor.fetchall()
        finally:
            conn.close()


def sanitize_description(desc: str) -> str:
    """Strictly cleans a prompt description by removing newlines and redundant spaces."""
    # Split by line breaks and join with a space to remove any newlines
    cleaned = " ".join(desc.splitlines())
    # Split by whitespace and rejoin to collapse multiple spaces into a single space
    return " ".join(cleaned.split())


def export_to_json(pid: int, desc: str) -> None:
    """Sanitizes description and exports the record information into a JSON file."""
    clean_json_desc = sanitize_description(desc)
    data = {"record_id": pid, "description": clean_json_desc}

    file_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        initialfile=f"pixel_export_{pid}.json",
        filetypes=[("JSON files", "*.json")],
    )

    if file_path:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", f"Record #{pid} exported!")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save JSON: {e}")


class RightClickMenu:
    """Context menu overlay providing basic editing tasks (Copy, Paste, Select All)."""

    def __init__(self, widget: tk.Widget) -> None:
        self.widget = widget
        self.menu = tk.Menu(
            widget,
            tearoff=0,
            bg=COLOR_CARD,
            fg=COLOR_TEXT_PRIMARY,
            activebackground=COLOR_ACCENT,
            activeforeground=COLOR_TEXT_PRIMARY,
            bd=0,
        )
        self.menu.add_command(label="Copy", command=lambda: self.widget.event_generate("<<Copy>>"))
        self.menu.add_command(label="Paste", command=lambda: self.widget.event_generate("<<Paste>>"))
        self.menu.add_separator()
        self.menu.add_command(label="Select All", command=self._select_all)

        self.widget.bind("<Button-3>", self._show_menu)

    def _select_all(self) -> None:
        if isinstance(self.widget, tk.Text):
            self.widget.tag_add("sel", "1.0", "end")
        elif isinstance(self.widget, tk.Entry):
            self.widget.select_range(0, tk.END)
            self.widget.icursor(tk.END)

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)


class ModernButton(tk.Button):
    """A customized tk.Button with modern flat styling and hover animations."""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: any = None,
        bg_color: str = COLOR_ACCENT,
        hover_bg: str = COLOR_ACCENT_HOVER,
        fg_color: str = COLOR_TEXT_PRIMARY,
        hover_fg: str = COLOR_TEXT_PRIMARY,
        font: tuple = ("Segoe UI", 10, "bold"),
        padx: int = 15,
        pady: int = 8,
        width: int | None = None,
        bd: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            font=font,
            bd=bd,
            relief=tk.FLAT,
            activebackground=hover_bg,
            activeforeground=hover_fg,
            padx=padx,
            pady=pady,
            cursor="hand2",
            **kwargs,
        )
        if width is not None:
            self.configure(width=width)

        self.normal_bg = bg_color
        self.hover_bg = hover_bg
        self.normal_fg = fg_color
        self.hover_fg = hover_fg

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event: tk.Event) -> None:
        self.configure(bg=self.hover_bg, fg=self.hover_fg)

    def _on_leave(self, event: tk.Event) -> None:
        self.configure(bg=self.normal_bg, fg=self.normal_fg)


class GalleryWindow(tk.Toplevel):
    """Gallery popup window to search and view existing entries."""

    def __init__(self, parent: tk.Tk, db: DatabaseManager) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db = db
        self.title("PixelPrompt Gallery ⬢")
        self.geometry("1150x850")
        self.configure(bg=COLOR_BG)

        # Search Bar Header
        search_frame = tk.Frame(self, bg=COLOR_CARD, pady=15)
        search_frame.pack(fill=tk.X)

        tk.Label(
            search_frame,
            text="⬢ SEARCH VAULT:",
            bg=COLOR_CARD,
            fg=COLOR_TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=20)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=30,
            font=("Segoe UI", 11),
            bg=COLOR_BG,
            fg=COLOR_TEXT_PRIMARY,
            insertbackground=COLOR_TEXT_PRIMARY,
            bd=0,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_ACCENT,
            highlightthickness=1,
        )
        self.search_entry.pack(side=tk.LEFT, padx=5, ipady=3)
        RightClickMenu(self.search_entry)

        self.btn_extract = ModernButton(
            search_frame,
            text="EXTRACT",
            command=self.run_search,
            bg_color=COLOR_ACCENT,
            hover_bg=COLOR_ACCENT_HOVER,
            fg_color=COLOR_TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold"),
            padx=15,
            pady=3,
        )
        self.btn_extract.pack(side=tk.LEFT, padx=10)

        # Canvas & Scrollbar setup for multi-column gallery layout
        self.canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.gallery_frame = tk.Frame(self.canvas, bg=COLOR_BG)
        self.canvas.create_window((0, 0), window=self.gallery_frame, anchor="nw")

        self.search_entry.bind("<Return>", lambda e: self.run_search())

    def run_search(self) -> None:
        """Fetches records matching query and updates results view grid."""
        query = self.search_var.get().strip()

        # Remove previous results
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()

        if not query:
            return

        records = self.db.search_records(query)

        col, row = 0, 0
        for pid, desc, blob in records:
            cell = tk.Frame(
                self.gallery_frame,
                bg=COLOR_CARD,
                padx=12,
                pady=12,
                highlightbackground=COLOR_BORDER,
                highlightthickness=1,
            )
            cell.grid(row=row, column=col, padx=15, pady=15)

            if blob:
                try:
                    img = Image.open(io.BytesIO(blob))
                    img.thumbnail((220, 220))
                    photo = ImageTk.PhotoImage(img)
                    img_label = tk.Label(cell, image=photo, bg=COLOR_CARD)
                    img_label.image = photo  # Prevent garbage collection of image object
                    img_label.pack()
                except Exception:
                    pass

            tk.Label(
                cell,
                text=f"⬢ RECORD #{pid}",
                fg=COLOR_ACCENT,
                bg=COLOR_CARD,
                font=("Segoe UI", 9, "bold"),
            ).pack(pady=(4, 0))

            desc_box = tk.Text(
                cell,
                width=28,
                height=5,
                bg=COLOR_BG,
                fg=COLOR_TEXT_PRIMARY,
                insertbackground=COLOR_TEXT_PRIMARY,
                font=("Segoe UI", 9),
                bd=0,
                padx=8,
                pady=8,
                relief=tk.FLAT,
            )
            desc_box.insert("1.0", desc)
            desc_box.pack(pady=5)
            RightClickMenu(desc_box)

            btn_frame = tk.Frame(cell, bg=COLOR_CARD)
            btn_frame.pack(fill=tk.X, pady=(8, 0))

            ModernButton(
                btn_frame,
                text="COPY PROMPT",
                command=lambda text=desc: self.copy_prompt(text),
                bg_color=COLOR_BORDER,
                hover_bg=COLOR_ACCENT,
                fg_color=COLOR_TEXT_PRIMARY,
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=4,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

            ModernButton(
                btn_frame,
                text="JSON ⬡",
                command=lambda p=pid, d=desc: export_to_json(p, d),
                bg_color=COLOR_ACCENT,
                hover_bg=COLOR_ACCENT_HOVER,
                fg_color=COLOR_TEXT_PRIMARY,
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=4,
            ).pack(side=tk.RIGHT, padx=(2, 0))

            col += 1
            if col >= 3:
                col = 0
                row += 1

        self.gallery_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def copy_prompt(self, text: str) -> None:
        """Copies the given description prompt to the clipboard."""
        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)


class PixelPromptApp:
    """The main interface application logic and layout."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PixelPrompt ⬢")
        self.root.geometry("650x700")
        self.root.configure(bg=COLOR_BG)

        self.db = DatabaseManager()
        self.image_path_var = tk.StringVar()

        tk.Label(
            self.root,
            text="⬢  PIXELPROMPT VAULT  ⬢",
            bg=COLOR_BG,
            fg=COLOR_ACCENT,
            font=("Segoe UI", 20, "bold"),
        ).pack(pady=25)

        tk.Label(
            self.root,
            text="INPUT PROMPT DESCRIPTION",
            bg=COLOR_BG,
            fg=COLOR_TEXT_MUTED,
            font=("Segoe UI", 10, "bold"),
        ).pack()

        self.desc_text = tk.Text(
            self.root,
            width=65,
            height=12,
            bg=COLOR_CARD,
            fg=COLOR_TEXT_PRIMARY,
            insertbackground=COLOR_TEXT_PRIMARY,
            font=("Consolas", 11),
            bd=0,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_ACCENT,
            highlightthickness=1,
            padx=12,
            pady=12,
            relief=tk.FLAT,
        )
        self.desc_text.pack(pady=10)
        RightClickMenu(self.desc_text)

        # Path display entry
        self.path_entry = tk.Entry(
            self.root,
            textvariable=self.image_path_var,
            width=60,
            bg=COLOR_BG,
            fg=COLOR_TEXT_MUTED,
            bd=0,
            highlightbackground=COLOR_BG,
            highlightcolor=COLOR_BG,
            highlightthickness=0,
            justify="center",
            font=("Segoe UI", 9),
        )
        self.path_entry.pack(pady=5)

        button_frame = tk.Frame(self.root, bg=COLOR_BG)
        button_frame.pack(pady=20)

        # Action layout buttons
        ModernButton(
            button_frame,
            text="SELECT IMAGE ⬡",
            command=self.browse_image,
            bg_color=COLOR_CARD,
            hover_bg=COLOR_BORDER,
            fg_color=COLOR_TEXT_PRIMARY,
            width=18,
        ).grid(row=0, column=0, padx=10, pady=5)

        ModernButton(
            button_frame,
            text="OPEN GALLERY ⬢",
            command=self.open_gallery,
            bg_color=COLOR_CARD,
            hover_bg=COLOR_BORDER,
            fg_color=COLOR_TEXT_PRIMARY,
            width=18,
        ).grid(row=0, column=1, padx=10, pady=5)

        ModernButton(
            button_frame,
            text="SAVE TO VAULT ⬢",
            command=self.save_data,
            bg_color=COLOR_ACCENT,
            hover_bg=COLOR_ACCENT_HOVER,
            fg_color=COLOR_TEXT_PRIMARY,
            font=("Segoe UI", 11, "bold"),
            width=38,
            pady=12,
        ).grid(row=1, column=0, columnspan=2, pady=15)

        self.bottom_label = tk.Label(
            self.root,
            text="─" * 45,
            bg=COLOR_BG,
            fg=COLOR_BORDER,
            font=("Segoe UI", 10),
        )
        self.bottom_label.pack(side=tk.BOTTOM, pady=15)

    def browse_image(self) -> None:
        """Browses system for images and stores path in path variable."""
        f_types = [("Images", "*.png *.jpg *.jpeg *.webp *.heic")]
        path = filedialog.askopenfilename(filetypes=f_types)
        if path:
            self.image_path_var.set(path)

    def save_data(self) -> None:
        """Sanitizes text, reads image path, and saves record entry into db."""
        raw_desc = self.desc_text.get("1.0", tk.END).strip()
        clean_desc = sanitize_description(raw_desc)
        path = self.image_path_var.get()

        if not clean_desc and not path:
            return

        try:
            image_blob = open(path, "rb").read() if path else None
            self.db.save_record(clean_desc, image_blob)
            messagebox.showinfo("Success", "Record Saved Successfully!")
            self.desc_text.delete("1.0", tk.END)
            self.image_path_var.set("")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def open_gallery(self) -> None:
        """Opens the gallery window modal."""
        GalleryWindow(self.root, self.db)


def main() -> None:
    """The main entry point of the PixelPrompt application."""
    root = tk.Tk()
    PixelPromptApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
