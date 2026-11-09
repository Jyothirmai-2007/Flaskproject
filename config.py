import mysql.connector
def connect():
    mydb=mysql.connector.connect(
        host="localhost",
        user="root",
        password="Akhil@2007",
        database="library_book_usage_db"
    )
    return mydb
