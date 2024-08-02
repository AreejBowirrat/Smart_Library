import tkinter as tk  # python 3
import datetime
import gspread
import pandas as pd
import openpyxl
import time


class SampleApp(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        # App Window Size::
        self.attributes('-fullscreen', True)

        # Create StatusBar
        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="top", fill="x")
        # Create and place the connection status label
        self.connection_status_label = tk.Label(self, font=("Arial", 20))
        self.connection_status_label.pack(anchor="ne", padx=20, pady=5)


        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (StartPage, UserStatusPage, MainUserPage, AdminPage, NotificationPage,
                  BorrowBookPage, ReturnBookPage, LoadingPage, StartingUpPage, IDScanLoadingPage,
                  BorrowBookLoadingPage, ReturnBookLoadingPage, TransactionsLoadingPage,
                  AutomaticLogOutPage):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame

            # put all the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")


        frame = self.frames['StartingUpPage']
        frame.tkraise()
        self.update()


        # connection to database:
        self.db_url = ""
        self.gc = None
        self.db = None
        self.no_wifi_connection = False
        try:
            self.db_url = "https://docs.google.com/spreadsheets/d/144bmhnqKytJMZwtBWR0IJ_UFbGy4gWWqukEfHV6laEU/edit?usp=sharing"
            self.gc = gspread.service_account(
                filename="./service_account.json")
            self.db = self.gc.open_by_url(self.db_url)
            # if control reaches here then there is WI-FI at startup, synchorinize with local database:
            TransactionsWorkSheet = self.db.worksheet("Transactions")
            TransactionsWorkSheet.clear()
            workbook = openpyxl.load_workbook('local_db.xlsx')

            # Select the worksheet (replace 'Sheet1' with the actual sheet name if different)
            transactions_worksheet = workbook["Transactions"]
            for row in transactions_worksheet.iter_rows(min_row=1, max_col=4):
                row_cells = [cell.value for cell in row]
                TransactionsWorkSheet.append_row(row_cells)
        except:
            self.no_wifi_connection = True


        # Variable to store Job Id of the currently scheduled logout job
        self.auto_logout_job = ""
        # Variable that stores the current state of the system to enable/disable auto logouts
        self.logged_in = False

        # Scheduled System Backup ( Copy google sheets to local Excel file):
        self.after(ms=600 * 1000, func=self.backup_data)  # backup every 10 minutes

        # db:
        self.Users = []

        self.Books = []

        self.Transactions = []

        self.update_connection_status()  # Initialize the connection status display
        self.frames["StartPage"].username_entry.focus_set()
        self.show_frame("StartPage")

    def update_connection_status(self):
        if self.no_wifi_connection:
            self.connection_status_label.config(text="❌ No Connection", fg="red")
        else:
            self.connection_status_label.config(text="Connected to WI-FI", fg="green")
        self.update()

    def convert_string(self, s):
        if not s[0].isnumeric():
            substring = s[1:10]
            result = substring
            return result
        else:
            return s

    def backup_data(self):
        # Schedule the next backup procedure:
        self.after(ms=600 * 1000, func=self.backup_data)  # every 10 minutes
        if self.logged_in:
            return  # don't want to bother the user

        self.show_frame('LoadingPage')
        try:
            self.sync_excel_to_google_sheet()
            self.update_connection_status()
            # if there's a WI-FI connection, load data from Google Sheets to local Excel file:
            sheets = ["Users", "Books", "Transactions", "Admins"]
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

        except:
            # control reached here so there's no WI-FI, nothing to backup but need to update connection status:
            self.no_wifi_connection = True
            self.update_connection_status()

        self.show_frame('StartPage')

    def show_frame(self, page_name):
        '''Show a frame for the given page name'''
        # update current page for auto log out
        if page_name != 'AutomaticLogOutPage':
            self.frames['AutomaticLogOutPage'].prev_page = page_name
        # delay the automatic logout since the user is interacting with the app:
        if page_name != 'StartPage' and self.logged_in is True:
            self.after_cancel(id=self.auto_logout_job)
            self.auto_logout_job = self.after(ms=60 * 1000, func=self.show_logout_warning)
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

        try:
            self.sync_excel_to_google_sheet()
            self.update_connection_status()

            # check if the Admin is logging in:
            Admins = self.db.worksheet("Admins").get_all_records()
            admin_info = None
            for a in Admins:
                if str(a['admin_id']) == self.remove_leading(id):
                    admin_info = a
                    break
            if admin_info is not None:
                self.logged_in = True
                self.auto_logout_job = self.after(ms=60 * 1000, func=self.show_logout_warning)
                self.goto_admin_page()
                return

            # if not the Admin, then check if one of the standard users:
            # get users list from cloud database:
            self.Users = self.db.worksheet("Users").get_all_records()
            user_info = None
            for u in self.Users:
                if str(u['user_id']) == self.remove_leading(id):
                    user_info = u
                    break
            if user_info is None:
                self.show_notification(notification="User does not exist!")
                self.frames['StartPage'].username_entry.delete(0, tk.END)
                self.show_frame('StartPage')
            else:
                self.logged_in = True
                self.auto_logout_job = self.after(ms=60 * 1000, func=self.show_logout_warning)
                self.frames['MainUserPage'].user_id = str(user_info['user_id'])
                self.show_frame("MainUserPage")

        except:
            # control reached here, so there is no WI-FI connection:
            self.no_wifi_connection = True
            self.update_connection_status()

            # In case there's no WI-FI connection:
            excel_file_path = "local_db.xlsx"
            # Open the workbook
            workbook = openpyxl.load_workbook(excel_file_path)

            # first, check if the Admin is logging in:
            admins_worksheet = workbook['Admins']
            admin_info = None
            for a in admins_worksheet.iter_rows(min_row=2, max_col=1):
                cell_value = a[0].value
                if str(cell_value) == self.remove_leading(id):
                    admin_info = cell_value
                    break
            if admin_info is not None:
                self.logged_in = True
                self.auto_logout_job = self.after(ms=60 * 1000, func=self.show_logout_warning)
                self.goto_admin_page()
                return

            # if not the Admin, check if it's one of the standard users:
            users_worksheet = workbook["Users"]
            user_info = None
            for row in users_worksheet.iter_rows(min_row=2, max_col=1):  # Skip the header row (assuming row 1)
                cell_value = row[0].value  # Access by index (0-based)
                if str(cell_value) == self.remove_leading(id):
                    user_info = cell_value
                    break
            if user_info is None:
                self.show_notification(notification="User does not exist!")
                self.frames['StartPage'].username_entry.delete(0, tk.END)
                self.show_frame('StartPage')
            else:
                self.logged_in = True
                self.auto_logout_job = self.after(ms=60 * 1000, func=self.show_logout_warning)
                self.frames['MainUserPage'].user_id = str(user_info)
                self.show_frame("MainUserPage")

    def logout(self):
        ''' clear login info from previous users and go back to start page: '''
        # cancel the currently scheduled auto log out job:
        self.after_cancel(id=self.auto_logout_job)
        # update system login status:
        self.logged_in = False
        # Log user out and go back to start page:
        self.frames["StartPage"].username_entry.delete(0, tk.END)
        self.frames['StartPage'].username_entry.focus_set()
        self.show_frame("StartPage")

    def goto_user_status_page(self, user_id, prev_page):
        self.show_frame('TransactionsLoadingPage')

        listbox = self.frames["UserStatusPage"].user_transactions_listbox
        listbox.delete(0, 'end')

        try:
            # check for WI-FI connection, if it came back sync data back to google sheet:
            self.sync_excel_to_google_sheet()
            self.update_connection_status()
            # If control reached here, then there is a WI-FI connection, get data from Google Sheets:
            self.Transactions = self.db.worksheet("Transactions").get_all_records()

            for t in self.Transactions:
                if str(t['user_id']) == self.remove_leading(user_id):
                    listbox.insert('end',
                                   "Book Name: " + str(t['book_name']) + "      Date of Borrow: " + str(t['date']))
        except:
            # control reached here so there is no WI-FI connection:
            self.no_wifi_connection = True
            self.update_connection_status()

            excel_file_path = "local_db.xlsx"
            # Open the workbook
            workbook = openpyxl.load_workbook(excel_file_path)
            # Select the worksheet (replace 'Sheet1' with the actual sheet name if different)
            transactions_worksheet = workbook["Transactions"]
            for row in transactions_worksheet.iter_rows(min_row=2, max_col=4):
                cell_value = row[0].value
                if str(cell_value) == self.remove_leading(user_id):
                    listbox.insert('end', "Book Name: " + str(row[2].value) + " Date: " + str(row[3].value))

        self.frames["UserStatusPage"].back_page = prev_page
        self.show_frame("UserStatusPage")

    def goto_admin_page(self):
        self.frames["AdminPage"].barcode_entry.delete(0, tk.END)
        self.frames["AdminPage"].barcode_entry.focus_set()
        self.show_frame("AdminPage")

    def goto_borrow_book_page(self, user_id):
        self.frames["BorrowBookPage"].user_id = user_id
        self.frames["BorrowBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["BorrowBookPage"].barcode_entry.focus_set()
        self.show_frame("BorrowBookPage")

    def goto_return_book_page(self):
        self.frames["ReturnBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["ReturnBookPage"].barcode_entry.focus_set()
        self.show_frame("ReturnBookPage")

    def return_book(self, barcode):
        self.show_frame('ReturnBookLoadingPage')

        try:
            # check for WI-FI connection, if it came back sync data back to google sheet:
            self.sync_excel_to_google_sheet()
            self.update_connection_status()
            # If control reached here, then there is a WI-FI connection, get data from Google Sheets:
            self.Transactions = self.db.worksheet("Transactions").get_all_records()
            TransactionsTable = self.db.worksheet("Transactions")
            index_to_delete = -1
            for index, t in enumerate(self.Transactions):
                if str(t['barcode']) == self.remove_leading(barcode):
                    index_to_delete = index
                    break
            if index_to_delete == -1:
                self.show_notification(notification="This Book Copy Has Not Been Borrowed Before!")
                self.frames['ReturnBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['ReturnBookPage'].barcode_entry.focus_set()
                self.show_frame('ReturnBookPage')
                return
            TransactionsTable.delete_rows(index_to_delete + 2, index_to_delete + 2)
        except:
            # control reached here so there is no WI-FI connection:
            self.no_wifi_connection = True
            self.update_connection_status()

            excel_file_path = "local_db.xlsx"
            # Open the workbook
            workbook = openpyxl.load_workbook(excel_file_path)

            # Select the worksheet (replace 'Sheet1' with the actual sheet name if different)
            transactions_worksheet = workbook["Transactions"]
            index_to_delete = -1
            for index, row in enumerate(transactions_worksheet.iter_rows(min_row=2, max_col=2)):
                cell_value = row[1].value
                if str(cell_value) == self.remove_leading(barcode):
                    index_to_delete = index
                    break
            if index_to_delete == -1:
                self.show_notification(notification="This Book Copy Has Not Been Borrowed Before!")
                self.frames['ReturnBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['ReturnBookPage'].barcode_entry.focus_set()
                self.show_frame('ReturnBookPage')
                return
            transactions_worksheet.delete_rows(idx=index_to_delete + 2, amount=1)
            workbook.save(filename=excel_file_path)

        self.show_notification(notification="Book Returned Successfully!")
        self.frames["ReturnBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["ReturnBookPage"].barcode_entry.focus_set()
        self.show_frame('ReturnBookPage')

    def remove_leading(self, barcode):
        return barcode.lstrip('0')

    def borrow_book(self, barcode, user_id):
        self.show_frame('BorrowBookLoadingPage')
        #####################################################################################################

        try:
            # check for WI-FI connection, if it came back sync data back to google sheet:
            self.sync_excel_to_google_sheet()
            self.update_connection_status()
            # If control reached here, then there is a WI-FI connection, get data from Google Sheets:
            self.Books = self.db.worksheet("Books").get_all_records()
            self.Transactions = self.db.worksheet("Transactions").get_all_records()

            # Check if the copy is available for borrow:
            book_info = None
            for b in self.Books:
                if str(b['barcode']) == self.remove_leading(barcode):
                    book_info = b
                    break
            if book_info == None:
                self.show_notification(notification="Book does not belong to the Library!")
                self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['BorrowBookPage'].barcode_entry.focus_set()
                self.show_frame('BorrowBookPage')
                return
            for t in self.Transactions:
                if str(t['barcode']) == self.remove_leading(barcode):
                    self.show_notification(notification="This Book Copy has not been returned yet!")
                    self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                    self.frames['BorrowBookPage'].barcode_entry.focus_set()
                    self.show_frame('BorrowBookPage')
                    return

            # Else, create and enter a new transaction record for user_id and book_barcode:
            transaction_date = datetime.date.today()
            transaction_date_str = transaction_date.strftime("%B %d, %Y")
            new_row_data = [int(user_id), int(barcode), book_info['book_name'], transaction_date_str]
            TransactionsWorkSheet = self.db.worksheet("Transactions")
            TransactionsWorkSheet.append_row(new_row_data)

        except:
            # control reached here so there is no WI-FI connection:
            self.no_wifi_connection = True
            self.update_connection_status()

            excel_file_path = "local_db.xlsx"
            # Open the workbook
            workbook = openpyxl.load_workbook(excel_file_path)

            # Select the worksheet (replace 'Sheet1' with the actual sheet name if different)
            books_worksheet = workbook["Books"]
            transactions_worksheet = workbook["Transactions"]

            book_info = None
            for row in books_worksheet.iter_rows(min_row=2, max_col=2):  # Skip the header row (assuming row 1)
                cell_value = row
                if str(cell_value[0].value) == self.remove_leading(barcode):
                    book_info = cell_value[1].value
                    break
            if book_info is None:
                self.show_notification(notification="Book does not belong to the Library!")
                self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['BorrowBookPage'].barcode_entry.focus_set()
                self.show_frame('BorrowBookPage')
                return
            for row in transactions_worksheet.iter_rows(min_row=2, max_col=1):
                cell_value = row[0].value
                if str(cell_value) == self.remove_leading(barcode):
                    self.show_notification(notification="This Book Copy has not been returned yet!")
                    self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                    self.frames['BorrowBookPage'].barcode_entry.focus_set()
                    self.show_frame('BorrowBookPage')
                    return

            # Else, create and enter a new transaction record for user_id and book_barcode:
            transaction_date = datetime.date.today()
            transaction_date_str = transaction_date.strftime("%B %d, %Y")
            new_row_data = [int(user_id), int(barcode), book_info, transaction_date_str]
            transactions_worksheet.append(new_row_data)
            workbook.save(filename=excel_file_path)

        self.show_notification(notification="Book Borrowed Successfully :)")
        self.frames["BorrowBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["BorrowBookPage"].barcode_entry.focus_set()
        self.show_frame('BorrowBookPage')

    def add_book(self, barcode):
        self.show_frame('LoadingPage')

        try:
            self.sync_excel_to_google_sheet()
            self.update_connection_status()
            self.Books = self.db.worksheet("Books").get_all_records()

            # Check if the copy already exists in the database:
            for b in self.Books:
                if str(b['barcode']) == self.remove_leading(barcode):
                    self.show_notification(notification="Book is already in the Library!")
                    self.frames["AdminPage"].barcode_entry.delete(0, tk.END)
                    self.frames["AdminPage"].barcode_entry.focus_set()
                    self.show_frame('AdminPage')
                    return

            # Else, create a new row in the Books table and add barcode
            new_row_data = [int(barcode), 'N/A']
            BooksWorkSheet = self.db.worksheet("Books")
            BooksWorkSheet.append_row(new_row_data)
            self.show_notification(notification="Book Added Successfully :)")
            self.frames["AdminPage"].barcode_entry.delete(0, tk.END)
            self.frames["AdminPage"].barcode_entry.focus_set()
            self.show_frame('AdminPage')

        except:
            # control reached here so there is no WI-FI connection:
            self.no_wifi_connection = True
            self.update_connection_status()
            self.show_notification('No WI-FI Connection!')
            self.logout()

    def show_logout_warning(self):
        # Schedule the next automatic logout job:
        self.auto_logout_job = self.after(ms=60 * 1000, func=self.show_logout_warning)

        # Set timer to logout in 15 seconds if we got no user response:
        self.frames['AutomaticLogOutPage'].sched_logout = self.after(ms=15000, func=self.countdown_logout)

        # Now show the automatic logout message to user:
        self.show_frame('AutomaticLogOutPage')

    def countdown_logout(self):
        self.show_notification(notification="User Logged Out Automatically")
        self.logout()

    def show_notification(self, notification):
        self.frames['NotificationPage'].title_label.config(text=notification, font=('Helvetica', 25, 'bold'))
        self.show_frame('NotificationPage')
        time.sleep(2)

    def sync_excel_to_google_sheet(self):
        excel_file_path = 'local_db.xlsx'

        # check if there was no WI-FI connection at start-up:
        if self.db is None:
            self.db_url = "https://docs.google.com/spreadsheets/d/144bmhnqKytJMZwtBWR0IJ_UFbGy4gWWqukEfHV6laEU/edit?usp=sharing"
            self.gc = gspread.service_account(
                filename="./service_account.json")
            self.db = self.gc.open_by_url(self.db_url)

        TransactionsWorkSheet = self.db.worksheet("Transactions")
        # if control reaches here: then there is WI-FI

        if self.no_wifi_connection is True:
            # if control reaches here: this means there was no WI-FI connection and now it came back
            self.no_wifi_connection = False  # update connection status
            TransactionsWorkSheet.clear()
            workbook = openpyxl.load_workbook(excel_file_path)

            # Select the worksheet (replace 'Sheet1' with the actual sheet name if different)
            transactions_worksheet = workbook["Transactions"]
            for row in transactions_worksheet.iter_rows(min_row=1, max_col=4):
                row_cells = [cell.value for cell in row]
                TransactionsWorkSheet.append_row(row_cells)


class StartPage(tk.Frame):
    ''' Login Page: '''

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        # Label with larger font and padding
        label = tk.Label(self, text="Please Scan your ID Card or Enter Manually", font=("Arial", 20, "bold"))
        label.pack(side="top", fill="x", pady=20)  # Increased padding

        # Username label with smaller font

        # Entry with increased width
        self.username_entry = tk.Entry(self, width=30, font=("Helvetica", 26))
        self.username_entry.pack(pady=10)

        # Bind the Enter key to the username_entry widget
        self.username_entry.bind("<Return>", self.on_enter)

        # Create the numpad layou
        # t with larger font and padding
        button_frame = tk.Frame(self)
        button_frame.pack(side="top", pady=10)
        button_grid = [
            ['     1     ', '      2      ', '     3     '],
            ['     4     ', '      5      ', '     6     '],
            ['     7     ', '      8      ', '     9     '],
            ['     0      ', 'Clear', 'Login']
        ]

        for row_index, row in enumerate(button_grid):
            for col_index, number in enumerate(row):
                if number == 'Clear':
                    button = tk.Button(button_frame, text='🗑️ ' + number, bg='red', fg='white',
                                       command=self.handle_clear_button_click,
                                       font=("Helvetica", 20))
                elif number == 'Login':
                    button = tk.Button(button_frame, text='🔑 ' + number, bg='green', fg='white', font=("Helvetica", 20),
                                       command=lambda: controller.validate_login(self.username_entry.get()))
                else:
                    button = tk.Button(button_frame, text=number,
                                       command=lambda n=number: self.handle_num_button_click(n), bg='white',
                                       font=("Helvetica", 30))
                button.grid(row=row_index, column=col_index, sticky="nsew", padx=5,
                            pady=5)  # Increased padding between buttons

    def on_enter(self, event):
        self.controller.validate_login(self.username_entry.get())

    # Define functions for numpad interaction
    def handle_num_button_click(self, number):
        self.username_entry.insert(tk.END, number.strip())

    def handle_clear_button_click(self):
        self.username_entry.delete(0, tk.END)


class AdminPage(tk.Frame):  # for the admin to add books

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Add a new Book to Library", font=('Helvetica', 30, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        subtitle1_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                   font=('Helvetica', 20))
        subtitle1_label.pack(side="top", fill="x", pady=5)

        self.barcode_entry = tk.Entry(self, width=20, font=("Helvetica", 26))
        self.barcode_entry.pack(pady=10)

        subtitle2_label = tk.Label(self, text="Make sure to fill out the Book Name in the database after scanning",
                                   font=('Helvetica', 20))
        subtitle2_label.pack(side="top", fill="x", pady=5)

        logout_button = tk.Button(self, text='🔙 ' + "Logout",
                                  command=lambda: controller.logout(),
                                  font=('Helvetica', 30))
        logout_button.pack(pady=10)

        # Bind the Enter key to the barcode_entry widget
        self.barcode_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.add_book(self.barcode_entry.get())


class MainUserPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Hello, user" + ' 📚', font=('Helvetica', 35, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        button_frame = tk.Frame(self)
        button_frame.pack(side="top", pady=10)
        borrow_book_button = tk.Button(button_frame,
                                       text="Borrow" +"\n"+ " (➕📖) ",
                                       command=lambda: controller.goto_borrow_book_page(user_id=self.user_id),
                                       bg="green", fg='white', font=('Helvetica', 25, 'bold'),
                                       width=15, height=8)
        borrow_book_button.pack(side="left", padx=10)

        # Return button
        return_book_button = tk.Button(button_frame,
                                       text="Return" +"\n"+" (➖📗) ",
                                       command=lambda: controller.goto_return_book_page(),
                                       font=('Helvetica', 25, 'bold'),
                                       bg="red", fg='white', width=15, height=8)
        return_book_button.pack(side="left", padx=10)

        # History button
        view_transactions_button = tk.Button(button_frame,
                                             text="History" +"\n"+ " 📑",
                                             command=lambda: controller.goto_user_status_page(
                                                 user_id=self.user_id,
                                                 prev_page="MainUserPage"),
                                             bg="blue", fg='white',
                                             font=('Helvetica', 25, 'bold'),
                                             width=15, height=8)
        view_transactions_button.pack(side="left", padx=10)

        # Logout button
        logout_button = tk.Button(self, text="Logout" + " 👋",
                                  command=lambda: controller.logout(), bg='black', fg='white',
                                  font=('Helvetica', 25, 'bold'))
        logout_button.pack(side="top", pady=(10, 10))


class UserStatusPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Books You've Borrowed", font=('Helvetica', 30, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        self.user_transactions_listbox = tk.Listbox(
            self,
            exportselection=False,
            selectmode=tk.SINGLE,
            font=('Helvetica', 25, 'bold'))

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
        title_label = tk.Label(self, text="Loading, Please Wait...", font=('Helvetica', 25, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

class StartingUpPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Starting Up, Please Wait...", font=('Helvetica', 25, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class IDScanLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Logging in, Please Wait...", font=('Helvetica', 30, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class BorrowBookLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Registering Book Borrow, Please Wait...", font=('Helvetica', 25, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class ReturnBookLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Registering Book Return, Please Wait...", font=('Helvetica', 25, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class NotificationPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.title_label = tk.Label(self, text="")
        self.title_label.pack(side="top", fill="x", pady=10)


class TransactionsLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Fetching Data, Please Wait...", font=('Helvetica', 30, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)


class BorrowBookPage(tk.Frame):  # for the user

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Borrow A Book", font=('Helvetica', 30, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=('Helvetica', 20, "bold"))
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
        title_label = tk.Label(self, text="Return A Book", font=('Helvetica', 30, 'bold'))
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=('Helvetica', 20, 'bold'))
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


class AutomaticLogOutPage(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        line1 = tk.Label(self, text="We Noticed You've Been Logged In For A While,",
                         font=('Helvetica', 25, 'bold'))

        line1.pack(side="top", fill="x", pady=10)

        line2 = tk.Label(self, text="Are You Still There? Please Confirm Or You'll",
                         font=('Helvetica', 17, 'bold'))

        line2.pack(side="top", fill="x", pady=10)

        line3 = tk.Label(self, text="Be Logged Out Automatically In 15 Seconds",
                         font=('Helvetica', 17, 'bold'))

        line3.pack(side="top", fill="x", pady=10)

        # Variable to store the page when this message pops up:
        self.prev_page = ""

        # Variable to store the scheduled logout job:
        self.sched_logout = None

        # Create and pack 'Yes' and 'No' buttons
        button_frame = tk.Frame(self)
        button_frame.pack(pady=30)

        yes_button = tk.Button(button_frame, text="Yes, still here!" + " ✅", command=self.stay,
                               fg="green", font=('Helvetica', 25, 'bold'))
        yes_button.pack(side="left", padx=10)

        no_button = tk.Button(button_frame, text="No, log me out" + " ❌", command=self.leave,
                              fg="red", font=('Helvetica', 25, 'bold'))
        no_button.pack(side="right", padx=10)

    def stay(self):
        # here cancel the scheduled logout
        self.after_cancel(id=self.sched_logout)
        self.controller.show_frame(self.prev_page)

    def leave(self):
        # here cancel the scheduled logout
        self.after_cancel(id=self.sched_logout)
        self.controller.logout()


class StatusBar(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent, height=50)  # Increased height for better visibility
        self.pack(side="top", fill="x")

        # Time Label
        self.time_label = tk.Label(self, font=("Helvetica", 20))  # Increased font size
        self.time_label.pack(side="left", padx=20, pady=(30, 0))  # Increased padding

        # Date Label
        self.date_label = tk.Label(self, font=("Helvetica", 20))  # Increased font size
        self.date_label.pack(side="right", padx=20, pady=(35, 0))  # Increased padding

        # Update time and date every second
        self.update_time()

    def update_time(self):
        now = datetime.datetime.now()
        self.time_label.config(text=now.strftime("%H:%M"))
        self.date_label.config(text=now.strftime("%Y-%m-%d"))
        self.after(60 * 1000, self.update_time)  # Update every minute


if __name__ == "__main__":
    app = SampleApp()
    app.mainloop()