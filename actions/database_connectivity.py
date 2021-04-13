import mysql.connector

def DataUpdate(Name,Number,Email):
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        passwd="****",
        database="mydatabase"
        )

    mycursor =mydb.cursor()
    
    #sql = "CREATE TABLE User_Details (Name VARCHAR(255), Number VARCHAR(255), Email VARCHAR(255));"
    sql = 'INSERT INTO User_Details (Name,Number,Email) VALUES ("{0}","{1}","{2}");'.format(Name,Number,Email)
    mycursor.execute(sql)
    
    mydb.commit()
    
    print(mycursor.rowcount,"record inserted")