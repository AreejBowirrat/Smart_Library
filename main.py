
import tkinter as tk                # python 3
from tkinter import font as tkfont  # python 3
from tkinter import messagebox
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
        self.geometry("800x600")

        # Initialize connection to database:
        self.db_url = "https://docs.google.com/spreadsheets/d/144bmhnqKytJMZwtBWR0IJ_UFbGy4gWWqukEfHV6laEU/edit?usp=sharing"
        self.gc = gspread.service_account(
            filename="./service_account.json")
        self.db = self.gc.open_by_url(self.db_url)

        # Scheduled System Backup:
        #self.backup_data()
        #schedule.every().hour.do(self.backup_data)

        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
        self.subtitle_font = tkfont.Font(family='Helvetica', size=13, weight="bold", slant="italic")
        self.normal_font = tkfont.Font(family='Helvetica', size=11, weight="bold", slant="italic")
        self.list_font = tkfont.Font(family='Helvetica', size=14, weight="bold", slant="italic")

        # db:
        self.Users = []

        self.Books = []

        self.Transactions = []




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

            # put all of the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")


        self.frames["StartPage"].username_entry.focus_set()
        self.show_frame("StartPage")


    def convert_string(self, s):
        if not s[0].isnumeric():
            substring = s[1:10]
            result = substring
            return result
        else:
            return s



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



    def logout(self):
        ''' clear login info from previous users and go back to start page: '''
        self.frames["StartPage"].username_entry.delete(0, tk.END)
        self.frames['StartPage'].username_entry.focus_set()
        self.show_frame("StartPage")






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
        TransactionsTable.delete_rows(index_to_delete+2, index_to_delete+2)
        self.show_notification(notification="Book Returned Successfully!")
        self.frames["ReturnBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["ReturnBookPage"].barcode_entry.focus_set()
        self.show_frame('ReturnBookPage')



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



    def show_notification(self, notification):
        self.frames['NotificationPage'].title_label.config(text=notification)
        self.show_frame('NotificationPage')
        time.sleep(2)




class StartPage(tk.Frame):
    ''' Login Page: '''

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        # Label with larger font and padding
        label = tk.Label(self, text="Please Scan your ID Card or Enter Manually", font=("Arial", 18, "bold"))
        label.pack(side="top", fill="x", pady=20)  # Increased padding

        # Username label with smaller font
        username_label = tk.Label(self, text="User ID:", font=("Helvetica", 14))
        username_label.pack(pady=3)

        # Entry with increased width
        self.username_entry = tk.Entry(self, width=25, font=("Helvetica", 16))
        self.username_entry.pack(pady=10)


        # Bind the Enter key to the username_entry widget
        self.username_entry.bind("<Return>", self.on_enter)

        # Create the numpad layout with larger font and padding
        button_frame = tk.Frame(self)
        button_frame.pack(side="top", pady=10)
        button_grid = [
            ['   7   ', '  8  ', '   9   '],
            ['   4   ', '  5  ', '   6   '],
            ['   1   ', '  2  ', '   3   '],
            ['   0   ', 'Clear', 'Login']  # Add '.' for decimal input if needed
        ]

        for row_index, row in enumerate(button_grid):
            for col_index, number in enumerate(row):
                if number == 'Clear':
                    button = tk.Button(button_frame, text=number, command=self.handle_clear_button_click,
                                       font=("Helvetica", 20))
                elif number == 'Login':
                    button = tk.Button(button_frame, text=number, font=("Helvetica", 20),
                              command=lambda: controller.validate_login(self.username_entry.get()))
                else:
                    button = tk.Button(button_frame, text=number, command=lambda n=number: self.handle_num_button_click(n),
                                       font=("Helvetica", 20))
                button.grid(row=row_index, column=col_index, sticky="nsew", padx=5, pady=5)  # Increased padding between buttons

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
        title_label = tk.Label(self, text="Hello, user", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)



        borrow_book_button = tk.Button(self, text="Borrow a Book",
                                       command=lambda: controller.goto_borrow_book_page(user_id=self.user_id),
                                       font=('Helvetica', 17, 'bold'))
        borrow_book_button.pack(pady=10)


        return_book_button = tk.Button(self, text="Return a Book",
                                       command=lambda: controller.goto_return_book_page(),
                                       font=('Helvetica', 17, 'bold'))
        return_book_button.pack(pady=10)



        self.user_id = None
        view_transactions_button = tk.Button(self, text="View my Trasnsactions",
                                             command=lambda: controller.goto_user_status_page(
                                                 user_id=self.user_id,
                                                 prev_page="MainUserPage"),
                                             font=('Helvetica', 17, 'bold'))
        view_transactions_button.pack(pady=10)

        logout_button = tk.Button(self, text="Logout",
                                  command=lambda: controller.logout(),
                                  font=('Helvetica', 14))
        logout_button.pack(pady=5)



class UserStatusPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="User Transactions Status", font=controller.title_font)
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
        back_button = tk.Button(self, text="Go Back",
                           command=lambda: controller.show_frame(self.back_page))
        back_button.pack()





class LoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Loading, Please Wait...", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)



class IDScanLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Scanning ID Card, Please Wait...", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)



class BorrowBookLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Registering Book Borrow, Please Wait...", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)



class ReturnBookLoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Registering Book Return, Please Wait...", font=controller.title_font)
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
        title_label = tk.Label(self, text="Fetching Transactions Data, Please Wait...", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)



class BorrowBookPage(tk.Frame): # for the user

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Borrow A Book", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=('Helvetica', 16))
        subtitle_label.pack(side="top", fill="x", pady=5)

        self.barcode_entry = tk.Entry(self)
        self.barcode_entry.pack(pady=10)

        self.user_id = ""


        back_button = tk.Button(self, text="Go Back",
                                  command=lambda: controller.show_frame("MainUserPage"),
                                font=('Helvetica', 13))
        back_button.pack(pady=10)

        # Bind the Enter key to the barcode_entry widget
        self.barcode_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.borrow_book(self.barcode_entry.get(), self.user_id)




class ReturnBookPage(tk.Frame): # for the user

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Return A Book", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=('Helvetica', 16))
        subtitle_label.pack(side="top", fill="x", pady=10)

        self.barcode_entry = tk.Entry(self)
        self.barcode_entry.pack(pady=10)



        back_button = tk.Button(self, text="Go Back",
                                  command=lambda: controller.show_frame("MainUserPage"),
                                font=('Helvetica', 14))
        back_button.pack(pady=10)

        # Bind the Enter key to the barcode_entry widget
        self.barcode_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.return_book(self.barcode_entry.get())






if __name__ == "__main__":

    app = SampleApp()
    app.mainloop()




