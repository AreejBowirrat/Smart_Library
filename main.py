


import tkinter as tk                # python 3
from tkinter import font as tkfont  # python 3
from tkinter import messagebox
import datetime
import schedule
import gspread
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

        schedule.every().hour.do(self.backup_data)

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
        for F in (StartPage, UserStatusPage, BookInfoPage, MainUserPage,
                  BorrowBookPage, ReturnBookPage, LoadingPage):
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
        if s[0] == ";" or s[0] == "?" or s[0] == "+":
            substring = s[1:10]
            result = substring
            return result
        else:
            return s

    def backup_data(self):
        # Backup data on the Excel file on the Cloud
        pass




    def show_frame(self, page_name):
        '''Show a frame for the given page name'''
        frame = self.frames[page_name]
        frame.tkraise()

    def validate_login(self, id):

        if id == "":
            messagebox.showerror("Error", "Empty Fields")
            return

        id = self.convert_string(id)


        # check if the user exists:
        # get users list from cloud database:
        self.Users = self.db.worksheet("Users").get_all_records()
        user_info = None
        for u in self.Users:
            if str(u['user_id']) == id:
                user_info = u
                break
        if user_info is None:
            messagebox.showerror("Error", "User does not exist")
            self.frames['StartPage'].username_entry.delete(0, tk.END)
        else:
            self.frames['MainUserPage'].user_id = str(user_info['user_id'])
            self.show_frame("MainUserPage")



    def logout(self):
        ''' clear login info from previous users and go back to start page: '''
        self.frames["StartPage"].username_entry.delete(0, tk.END)
        self.frames['StartPage'].username_entry.focus_set()
        self.show_frame("StartPage")







    def goto_user_status_page(self, user_id, prev_page):
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
        self.Transactions = self.db.worksheet("Transactions").get_all_records()
        TransactionsTable = self.db.worksheet("Transactions")
        index_to_delete = -1
        for index, t in enumerate(self.Transactions):
            if str(t['barcode']) == barcode:
                index_to_delete = index
                break
        if index_to_delete == -1:
            messagebox.showerror("Error", "This copy isn't borrowed")
            self.frames['ReturnBookPage'].barcode_entry.delete(0, tk.END)
            self.frames['ReturnBookPage'].barcode_entry.focus_set()
            return
        TransactionsTable.delete_rows(index_to_delete+2, index_to_delete+2)
        messagebox.showinfo("Success", "Book Returned Successfully")
        self.frames["ReturnBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["ReturnBookPage"].barcode_entry.focus_set()



    def borrow_book(self, barcode, user_id):
        self.Books = self.db.worksheet("Books").get_all_records()
        self.Transactions = self.db.worksheet("Transactions").get_all_records()
        # Check if the copy is available for borrow:

        book_info = None
        for b in self.Books:
            if str(b['barcode']) == barcode:
                book_info = b
                break
        if book_info == None:
            messagebox.showerror("Error", "Book does not belong to the Library")
            self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
            self.frames['BorrowBookPage'].barcode_entry.focus_set()
            return
        for t in self.Transactions:
            if str(t['barcode']) == barcode:
                self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['BorrowBookPage'].barcode_entry.focus_set()
                messagebox.showerror("Error", "This Book Copy has not been returned yet")
                return
            if str(t['book_name']) == str(book_info['book_name']) and str(t['user_id']) == user_id:
                messagebox.showerror("Error", "You already borrowed a copy of this Book")
                self.frames['BorrowBookPage'].barcode_entry.delete(0, tk.END)
                self.frames['BorrowBookPage'].barcode_entry.focus_set()
                return


        # Else, create and enter a new transaction record for user_id and book_barcode:
        transaction_date = datetime.date.today()
        transaction_date_str = transaction_date.strftime("%Y-%m-%d")
        new_row_data = [user_id, barcode, book_info['book_name'], transaction_date_str]
        TransactionsWorkSheet = self.db.worksheet("Transactions")
        TransactionsWorkSheet.append_row(new_row_data)
        messagebox.showinfo("Success", "Transaction success")
        self.frames["BorrowBookPage"].barcode_entry.delete(0, tk.END)
        self.frames["BorrowBookPage"].barcode_entry.focus_set()





class StartPage(tk.Frame):
    ''' Login Page: '''
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        label = tk.Label(self, text="Please Scan your ID Card", font=controller.title_font)
        label.pack(side="top", fill="x", pady=10)

        username_label = tk.Label(self, text="User ID:", font=controller.subtitle_font)
        username_label.pack()

        self.username_entry = tk.Entry(self)
        self.username_entry.pack()


        login_button = tk.Button(self, text="Login",
                                 command=lambda: controller.validate_login(self.username_entry.get()))
        login_button.pack()

        # Bind the Enter key to the username_entry widget
        self.username_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.validate_login(self.username_entry.get())






class MainUserPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Hello, user", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)

        logout_button = tk.Button(self, text="Logout",
                                  command=lambda: controller.logout(),
                                  font=controller.normal_font)
        logout_button.pack(pady=3)


        subtitle_label2 = tk.Label(self, text="Book Management", font=controller.subtitle_font)
        subtitle_label2.pack(side="top", fill="x", pady=10)


        borrow_book_button = tk.Button(self, text="Borrow a Book",
                                       command=lambda: controller.goto_borrow_book_page(user_id=self.user_id),
                                       font=controller.normal_font)
        borrow_book_button.pack(pady=5)

        return_book_button = tk.Button(self, text="Return a Book",
                                       command=lambda: controller.goto_return_book_page(),
                                       font=controller.normal_font)
        return_book_button.pack(pady=5)



        self.user_id = None
        view_transactions_button = tk.Button(self, text="View my Trasnsactions",
                                             command=lambda: controller.goto_user_status_page(
                                                 user_id=self.user_id,
                                                 prev_page="MainUserPage"),
                                             font=controller.normal_font)
        view_transactions_button.pack(pady=5)







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





class BookInfoPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Book Info:", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label1 = tk.Label(self, text="Book Name:", font=controller.subtitle_font)
        subtitle_label1.pack(side="top", fill="x", pady=7)

        #self.course = None
        self.book_name_label = tk.Label(self, text="", font=controller.normal_font)
        self.book_name_label.pack(side="top", fill="x", pady=7)


        subtitle_label4 = tk.Label(self, text="Available Copies:", font=controller.subtitle_font)
        subtitle_label4.pack(side="top", fill="x", pady=7)

        self.available_copies_label = tk.Label(self, text="", font=controller.normal_font)
        self.available_copies_label.pack(side="top", fill="x", pady=8)


        self.back_page = None
        back_button = tk.Button(self, text="Go Back",
                           command=lambda: controller.show_frame(self.back_page))
        back_button.pack()




class LoadingPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Loading, Please Wait...", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)






class BorrowBookPage(tk.Frame): # for the user

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        title_label = tk.Label(self, text="Borrow A Book", font=controller.title_font)
        title_label.pack(side="top", fill="x", pady=10)

        subtitle_label = tk.Label(self, text="Please scan the book's barcode using the barcode scanner:",
                                  font=controller.subtitle_font)
        subtitle_label.pack(side="top", fill="x", pady=10)

        self.barcode_entry = tk.Entry(self)
        self.barcode_entry.pack()

        self.user_id = ""
        scan_book_button = tk.Button(self, text="Borrow Book",
                           command=lambda: controller.borrow_book(barcode=self.barcode_entry.get(), user_id=self.user_id),
                                     font=controller.normal_font)
        scan_book_button.pack(pady=10)

        back_button = tk.Button(self, text="Go Back",
                                  command=lambda: controller.show_frame("MainUserPage"),
                                font=controller.normal_font)
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
                                  font=controller.subtitle_font)
        subtitle_label.pack(side="top", fill="x", pady=10)

        self.barcode_entry = tk.Entry(self)
        self.barcode_entry.pack(pady=10)


        scan_book_button = tk.Button(self, text="Return Book",
                           command=lambda: controller.return_book(barcode=self.barcode_entry.get()),
                                     font=controller.normal_font)
        scan_book_button.pack(pady=10)


        back_button = tk.Button(self, text="Go Back",
                                  command=lambda: controller.show_frame("MainUserPage"),
                                font=controller.normal_font)
        back_button.pack(pady=10)

        # Bind the Enter key to the barcode_entry widget
        self.barcode_entry.bind("<Return>", self.on_enter)

    def on_enter(self, event):
        self.controller.return_book(self.barcode_entry.get())







if __name__ == "__main__":

    app = SampleApp()
    app.mainloop()




