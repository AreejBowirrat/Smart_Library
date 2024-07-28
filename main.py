

import tkinter as tk  # python 3
from tkinter import font as tkfont  # python 3
import datetime
import schedule
import gspread
import pandas as pd
from openpyxl import load_workbook
import csv
import time


class SampleApp(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        # App Window Size:
        self.attributes('-fullscreen', True)
        # self.geometry("800x600")

        # Initialize connection to database:
        self.db_url = "https://docs.google.com/spreadsheets/d/144bmhnqKytJMZwtBWR0IJ_UFbGy4gWWqukEfHV6laEU/edit?usp=sharing"
        self.gc = gspread.service_account(
            filename="./service_account.json")
        self.db = self.gc.open_by_url(self.db_url)
        self.logout_warning_popup = None  # Initialize as None
        self.logout_warning_timer = None  # Initialize as None
        # Scheduled System Backup:
        # self.backup_data()
        # schedule.every().hour.do(self.backup_data)

        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
        self.subtitle_font = tkfont.Font(family='Helvetica', size=13, weight="bold", slant="italic")
        self.normal_font = tkfont.Font(family='Helvetica', size=11, weight="bold", slant="italic")
        self.list_font = tkfont.Font(family='Helvetica', size=14, weight="bold", slant="italic")

        # db:
        self.Users = []

        self.Books = []

        self.Transactions = []

        # Create StatusBar
        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="top", fill="x")

        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (StartPage, UserStatusPage, MainUserPage, NotificationPage,
                  BorrowBookPage, ReturnBookPage, LoadingPage, IDScanLoadingPage,
                  BorrowBookLoadingPage, ReturnBookLoadingPage, TransactionsLoadingPage):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame

            # put all the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")

        self.frames["StartPage"].username_entry.focus_set()
        self.show_frame("StartPage")

        # Automatic Logout
        self.logout_timer = None
        self.logout_warning_interval = 10000  # 10 seconds

    def convert_string(self, s):
        if not s[0].isnumeric():
            substring = s[1:10]
            result = substring
            return result
        else:
            return s

    def start_logout_timer(self):
        self.logout_timer = self.after(self.logout_warning_interval, self.show_logout_warning)

    def reset_logout_timer(self):
        """Reset the logout timer and close the logout warning popup if open."""
        if hasattr(self, 'logout_warning_timer'):
            self.after_cancel(self.logout_warning_timer)  # Cancel automatic logout timer
        if self.logout_timer:
            self.after_cancel(self.logout_timer)  # Cancel existing logout warning timer
        self.start_logout_timer()  # Restart the logout timer

        if hasattr(self, 'logout_warning_popup'):
            self.logout_warning_popup.destroy()  # Close the popup if it exists

        # if self.logout_timer:
        #     self.after_cancel(self.logout_timer)
        # self.start_logout_timer()

    def backup_data(self):
        self.show_frame('LoadingPage')
        sheets = ["Users", "Books", "Transactions"]
        google_sheets = [(sheet_name, self.db.worksheet(sheet_name).id) for sheet_name in sheets]
        excel_file = "./local_db.xlsx"  # Replace with path to your Excel file

        with pd.ExcelWriter(
                path=excel_file,
                mode="w",
                engine="openpyxl",
        ) as writer:
            for google_sheet in google_sheets:
                sheet_url = f"https://docs.google.com/spreadsheets/d/144bmhnqKytJMZwtBWR0IJ_UFbGy4gWWqukEfHV6laEU/" \
                            f"export?format=csv&gid={google_sheet[1]}"
                df = pd.read_csv(sheet_url)
                df.to_excel(writer, sheet_name=google_sheet[0], index=False)

        print("Data transferred successfully!")
        pass

    def show_frame(self, page_name):
        '''Show a frame for the given page name'''
        frame = self.frames[page_name]
        frame.tkraise()
        self.update()

    def validate_login(self, id):

        if id == "":
            self.show_notification(notification="Empty Fields")
            self.show_frame('StartPage')
            return

        id = self.convert_string(id)

        self.show_frame('IDScanLoadingPage')
        # check if the user exists:
        # get users list from cloud database:
        self.Users = self.db.worksheet("Users").get_all_records()
        user_info = None
        for u in self.Users:
            if str(u['user_id']) == id:
                user_info = u
                break
        if user_info is None:
            self.show_notification(notification="User does not exist!")
            self.frames['StartPage'].username_entry.delete(0, tk.END)
            self.show_frame('StartPage')
        else:
            self.frames['MainUserPage'].user_id = str(user_info['user_id'])
            self.show_frame("MainUserPage")
            self.start_logout_timer()  # Start the logout timer after successful login

    def logout(self):
        ''' clear login info from previous users and go back to start page: '''
        self.frames["StartPage"].username_entry.delete(0, tk.END)
        self.frames['StartPage'].username_entry.focus_set()
        self.show_frame("StartPage")
        if self.logout_timer:
            self.after_cancel(self.logout_timer)  # Cancel the logout timer if it exists

    def goto_user_status_page(self, user_id, prev_page):
        self.show_frame('TransactionsLoadingPage')

        listbox = self.frames["UserStatusPage"].user_transactions_listbox
        listbox.delete(0, 'end')
        # Get Transactions  Table from Google Sheets:
        self.Transactions = self.db.worksheet("Transactions").get_all_records()

        for t in self.Transactions:
            if str(t['user_id']) == user_id:
                listbox.insert('end', "Book Name: " + str(t['book_name']) + " Date: " + str(t['date']))
        self.frames["UserStatusPage"].back_page = prev_page
        self.show_frame("UserStatusPage")
        self.reset_logout_timer()

    def goto_borrow_book_page(self, user_id):
        self.frames["BorrowBookPage"].user_id = user_id
        self.frames["BorrowBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["BorrowBookPage"].barcode_entry.focus_set()
        self.show_frame("BorrowBookPage")
        self.reset_logout_timer()

    def goto_return_book_page(self):
        self.frames["ReturnBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["ReturnBookPage"].barcode_entry.focus_set()
        self.show_frame("ReturnBookPage")
        self.reset_logout_timer()

    def return_book(self, barcode):
        self.show_frame('ReturnBookLoadingPage')

        self.Transactions = self.db.worksheet("Transactions").get_all_records()
        TransactionsTable = self.db.worksheet("Transactions")
        index_to_delete = -1
        for index, t in enumerate(self.Transactions):
            if str(t['barcode']) == barcode:
                index_to_delete = index
                break
        if index_to_delete == -1:
            self.show_notification(notification="This Book Copy Has Not Been Borrowed Before!")
            self.frames['ReturnBookPage'].barcode_entry.delete(0, tk.END)
            self.frames['ReturnBookPage'].barcode_entry.focus_set()
            self.show_frame('ReturnBookPage')
            return
        TransactionsTable.delete_rows(index_to_delete + 2, index_to_delete + 2)
        self.show_notification(notification="Book Returned Successfully!")
        self.frames["ReturnBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["ReturnBookPage"].barcode_entry.focus_set()
        self.show_frame('ReturnBookPage')
        self.reset_logout_timer()

    def borrow_book(self, barcode, user_id):
        self.show_frame('BorrowBookLoadingPage')

        self.Books = self.db.worksheet("Books").get_all_records()
        self.Transactions = self.db.worksheet("Transactions").get_all_records()
        # Check if the copy is available for borrow:

        book_info = None
        for b in self.Books:
            if str(b['barcode']) == barcode:
                book_info = b
                break
        if book_info == None:
            self.show_notification(notification="Book does not belong to the Library!")
            self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
            self.frames['BorrowBookPage'].barcode_entry.focus_set()
            self.show_frame('BorrowBookPage')
            return
        for t in self.Transactions:
            if str(t['barcode']) == barcode:
                self.show_notification(notification="This Book Copy has not been returned yet!")
                self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['BorrowBookPage'].barcode_entry.focus_set()
                self.show_frame('BorrowBookPage')
                return

        # Else, create and enter a new transaction record for user_id and book_barcode:
        transaction_date = datetime.date.today()
        transaction_date_str = transaction_date.strftime("%Y-%m-%d")
        new_row_data = [user_id, barcode, book_info['book_name'], transaction_date_str]
        TransactionsWorkSheet = self.db.worksheet("Transactions")
        TransactionsWorkSheet.append_row(new_row_data)
        self.show_notification(notification="Book Borrowed Successfully :)")
        self.frames["BorrowBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["BorrowBookPage"].barcode_entry.focus_set()
        self.show_frame('BorrowBookPage')
        self.reset_logout_timer()

    def show_logout_warning(self):
        if self.logout_warning_popup:
            self.logout_warning_popup.destroy()

        self.logout_warning_popup = tk.Toplevel(self)
        self.logout_warning_popup.title("Logout Warning")

        # Set the popup window to be a smaller size and centered
        self.logout_warning_popup.geometry("400x200")
        self.logout_warning_popup.attributes('-topmost', 'true')  # Ensure the popup is always on top

        # Center the popup window
        window_width = 400
        window_height = 200
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.logout_warning_popup.geometry(f'{window_width}x{window_height}+{x}+{y}')

        # Create and pack the label with increased font size
        label1 = tk.Label(self.logout_warning_popup)
        label1.pack(pady=(30, 10))  # Padding to move label lower
        label = tk.Label(self.logout_warning_popup,
                         text="You will be logged out in 10 seconds. Do you want to stay logged in?",
                         font=('Helvetica', 30, 'bold'))

        label.pack(pady=10)

        # Create and pack 'Yes' and 'No' buttons
        button_frame = tk.Frame(self.logout_warning_popup)
        button_frame.pack(pady=10)

        yes_button = tk.Button(button_frame, text="Yes"+" ✅", command=self.reset_logout_timer, fg="green",
                               font=('Helvetica', 26, 'bold'))
        yes_button.pack(side="left", padx=10)

        no_button = tk.Button(button_frame, text="No"+" ❌", command=self.logout, fg="red", font=('Helvetica', 26, 'bold'))
        no_button.pack(side="left", padx=10)

        # Automatically log out after 10 seconds if no action is taken
        self.logout_warning_timer = self.after(10000, self.logout)

    def on_popup_close(self):
        """Handle the popup close event."""
        if hasattr(self, 'logout_warning_timer'):
            self.after_cancel(self.logout_warning_timer)  # Cancel the automatic logout timer
        self.logout_warning_popup.destroy()  # Destroy the popup

    def show_notification(self, notification):
        self.frames['NotificationPage'].title_label.config(text=notification, font=('Helvetica', 40, 'bold'))
        self.show_frame('NotificationPage')
        time.sleep(2)


class StartPage(tk.Frame):
    ''' Login Page: '''

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        # Label with larger font and padding
        label = tk.Label(self, text="Please Scan your ID Card or Enter Manually", font=("Arial", 35, "bold"))
        label.pack(side="top", fill="x", pady=20)  # Increased padding

        # Username label with smaller font
        username_label = tk.Label(self, text="User ID:", font=("Helvetica", 26))
        username_label.pack(pady=3)

        # Entry with increased width
        self.username_entry = tk.Entry(self, width=20, font=("Helvetica", 26))
        self.username_entry.pack(pady=10)

        # Bind the Enter key to the username_entry widget
        self.username_entry.bind("<Return>", self.on_enter)

        # Create the numpad layout with larger font and padding
        button_frame = tk.Frame(self)
        button_frame.pack(side="top", pady=10)
        button_grid = [
            ['   0   ', '   1   ', '   2   '],
            ['   3   ', '   4   ', '   5   '],
            ['   6   ', '   7   ', '   8   '],
            ['   9   ', 'Clear', 'Login']
        ]

        for row_index, row in enumerate(button_grid):
            for col_index, number in enumerate(row):
                if number == 'Clear':
                    button = tk.Button(button_frame, text='🗑️ ' + number, bg='red',
                                       command=self.handle_clear_button_click,
                                       font=("Helvetica", 20))
                elif number == 'Login':
                    button = tk.Button(button_frame, text='🔑 ' + number, bg='green', font=("Helvetica", 20),
                                       command=lambda: controller.validate_login(self.username_entry.get()))
                else:
                    button = tk.Button(button_frame, text=number,
                                       command=lambda n=number: self.handle_num_button_click(n),
                                       font=("Helvetica", 20))
                button.grid(row=row_index, column=col_index, sticky="nsew", padx=5,
                            pady=5)  # Increased padding between buttons

    def on_enter(self, event):
        self.controller.validate_login(self.username_entry.get())

    # Define functions for numpad interaction
    def handle_num_button_click(self, number):
        self.username_entry.insert(tk.END, number.strip())

    def handle_clear_button_click(self):
        self.username_entry.delete(0, tk.END)


class MainUserPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Hello, user" + ' 📚', font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=(20, 10))

        borrow_book_button = tk.Button(self,
                                       text="Borrow a Book"+"  (➕"+"📖)",
                                       command=lambda: controller.goto_borrow_book_page(user_id=self.user_id),
                                       font=('Helvetica', 26, 'bold'),
                                       width=20,  # Adjust width as needed
                                       height=3,
                                       borderwidth=10,  # Set border width
                                       relief="solid",  # Set border relief style
                                       highlightbackground="green",  # Set border color
                                       highlightcolor="green")  # Ensure border color is consistent
        # Adjust height as needed
        borrow_book_button.pack(padx=20, pady=10)  # Add padding around the button

        return_book_button = tk.Button(self,
                                       text= "Return a Book"+"  (➖"+"📕) ",
                                       command=lambda: controller.goto_return_book_page(),
                                       font=('Helvetica', 26, 'bold'),
                                       width=20,  # Adjust width as needed
                                       height=3,
                                       borderwidth=10,  # Set border width
                                       relief="solid",  # Set border relief style
                                       highlightbackground="red",  # Set border color
                                       highlightcolor="red")  # Ensure border color is consistent)  # Adjust height as needed
        return_book_button.pack(padx=20, pady=10)  # Add padding around the button

        self.user_id = None

        view_transactions_button = tk.Button(self, text="History Of Books You've Borrowed"+"  📜",
                                             command=lambda: controller.goto_user_status_page(
                                                 user_id=self.user_id,
                                                 prev_page="MainUserPage"),
                                             font=('Helvetica', 26, 'bold'),
                                             width=30,  # Adjust width as needed
                                             height=3,
                                             borderwidth=10,  # Set border width
                                             relief="solid",  # Set border relief style
                                             highlightbackground="blue",  # Set border color
                                             highlightcolor="blue")  # Ensure border color is consistent)  # Adjust height as needed)  # Adjust height as needed
        view_transactions_button.pack(padx=27, pady=10)  # Add padding around the button

        logout_button = tk.Button(self, text='👋 ' + "Logout",
                                  command=lambda: controller.logout(), bg="red",
                                  font=('Helvetica', 30))
        logout_button.pack(padx=15, pady=10)


class UserStatusPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Books You've Borrowed", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        self.user_transactions_listbox = tk.Listbox(
            self,
            exportselection=False,
            height=6,
            selectmode=tk.SINGLE,
            font=controller.list_font)

        self.user_transactions_listbox.pack(fill=tk.BOTH, side=tk.TOP, expand=True)

        # link a scrollbar to a list
        scrollbar = tk.Scrollbar(
            self.user_transactions_listbox,
            orient=tk.VERTICAL,
            command=self.user_transactions_listbox.yview
        )

        self.user_transactions_listbox['yscrollcommand'] = scrollbar.set

        scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)

        self.back_page = "userInfoPage"
        back_button = tk.Button(self, text='🔙 ' + "Go Back",
                                command=lambda: controller.show_frame(self.back_page),
                                font=('Helvetica', 30))
        back_button.pack(pady=10)


class LoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Loading, Please Wait...", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class IDScanLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Logging in, Please Wait...", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class BorrowBookLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Registering Book Borrow, Please Wait...", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class ReturnBookLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Registering Book Return, Please Wait...", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class NotificationPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.title_label = tk.Label(self, text="", font=controller.title_font)
        self.title_label.pack(side="top", fill="x", pady=10)


class TransactionsLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Fetching Data, Please Wait...", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=(20, 30))


class BorrowBookPage(tk.Frame):  # for the user

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Borrow A Book", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=('Helvetica', 35))
        subtitle_label.pack(side="top", fill="x", pady=5)

        self.barcode_entry = tk.Entry(self, width=20, font=("Helvetica", 26))
        self.barcode_entry.pack(pady=10)

        self.user_id = ""

        back_button = tk.Button(self, text='🔙 ' + "Go Back",
                                command=lambda: controller.show_frame("MainUserPage"),
                                font=('Helvetica', 30))
        back_button.pack(pady=10)

        # Bind the Enter key to the barcode_entry widget
        self.barcode_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.borrow_book(self.barcode_entry.get(), self.user_id)


class ReturnBookPage(tk.Frame):  # for the user

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Return A Book", font=('Helvetica', 40, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=('Helvetica', 35))
        subtitle_label.pack(side="top", fill="x", pady=10)

        self.barcode_entry = tk.Entry(self, width=20, font=("Helvetica", 26))
        self.barcode_entry.pack(pady=10)

        back_button = tk.Button(self, text='🔙 ' + "Go Back",
                                command=lambda: controller.show_frame("MainUserPage"),
                                font=('Helvetica', 30))
        back_button.pack(pady=10)

        # Bind the Enter key to the barcode_entry widget
        self.barcode_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.return_book(self.barcode_entry.get())


class StatusBar(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent, height=50)  # Increased height for better visibility
        self.pack(side="top", fill="x")

        # Time Label
        self.time_label = tk.Label(self, font=("Helvetica", 20, "bold"))  # Increased font size
        self.time_label.pack(side="left", padx=20)  # Increased padding

        # Date Label
        self.date_label = tk.Label(self, font=("Helvetica", 20, "bold"))  # Increased font size
        self.date_label.pack(side="right", padx=20)  # Increased padding

        # Update time and date every second
        self.update_time()

    def update_time(self):
        now = datetime.datetime.now()
        self.time_label.config(text=now.strftime("%H:%M:%S"))
        self.date_label.config(text=now.strftime("%Y-%m-%d"))
        self.after(1000, self.update_time)  # Update every second


if __name__ == "__main__":
    app = SampleApp()
    app.mainloop()