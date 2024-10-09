import streamlit as st
import mysql.connector
from mysql.connector import Error
import pandas as pd
import numpy as np
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import date

# Initialize session state variables if they don't exist
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'invoice' not in st.session_state:
    st.session_state['invoice'] = []

# MySQL Database connection
def create_connection():
    conn = None
    try:
        conn = mysql.connector.connect(
            host='sql12.freesqldatabase.com',
            user='sql12733953',
            password='YES',
            database='sql12733953'
        )
        if conn.is_connected():
            return conn
    except Error as e:
        st.error(f"Error connecting to MySQL database: {e}")
    return conn

def insert_invoice(conn, customer_info, total_invoice_price, rej, prev_due, amt, payment, due):
    try:
        cursor = conn.cursor()
        sql_insert_invoice = """
            INSERT INTO invoices (invoice_date, customer_name, customer_address, customer_mobile, previous_due, rejection, payment, new_due, final_amount, total_invoice_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        data = (
            customer_info['date'],
            customer_info['name'],
            customer_info['address'],
            customer_info['mobile'],
            prev_due,
            rej,
            payment,
            due,
            amt,
            total_invoice_price
        )
        cursor.execute(sql_insert_invoice, data)
        conn.commit()
        st.success("Invoice data stored successfully!")
    except Error as e:
        st.error(f"Error inserting invoice data: {e}")

# Retrieve product names from the database
def get_registered_products(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products")
        products = cursor.fetchall()
        return [product[0] for product in products]
    except Error as e:
        st.error(f"Error fetching products: {e}")
        return []

# Retrieve current stock for a product
def get_current_stock(conn, product_name):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT available_stock FROM products WHERE name = %s", (product_name,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Error as e:
        st.error(f"Error fetching current stock: {e}")
        return None

# Update product stock in the database
def update_product_stock(conn, product_name, new_stock):
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET available_stock = %s WHERE name = %s", (new_stock, product_name))
        conn.commit()
        st.success(f"Stock for {product_name} updated successfully!")
    except Error as e:
        st.error(f"Error updating product stock: {e}")

# Insert a product into the database
def insert_product(conn, name, dp_price, mrp_price, group_name, available_stock):
    try:
        if product_exists(conn, name):
            st.error("A product with this name already exists. Please use a different name.")
        else:
            sql_insert_product = """
                INSERT INTO products (name, dp_price, mrp_price, group_name, available_stock)
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor = conn.cursor()
            cursor.execute(sql_insert_product, (name, dp_price, mrp_price, group_name, available_stock))
            conn.commit()
            st.success("Product registered successfully!")
    except Error as e:
        st.error(f"Error inserting product: {e}")

# Check if product name already exists
def product_exists(conn, name):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE name = %s", (name,))
    return cursor.fetchone() is not None

# Function to fetch product details by name
def get_product_details_by_name(conn, product_name):
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM products WHERE name = %s", (product_name,))
        product = cursor.fetchone()
        return product
    except Error as e:
        st.error(f"Error fetching product details: {e}")
        return None

# Function to create PDF
def create_pdf(invoice_df, customer_info, total_invoice_price, rej, prev_due, amt, payment, due):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    def draw_page_header():
        c.drawString(250, height - 30, "M/S. ISHAQ ENTERPRISE")
        c.drawString(30, height - 50, f"Name: {customer_info['name']}")
        c.drawString(450, height - 50, f"Date: {customer_info['date']}")
        c.drawString(30, height - 70, f"Address: {customer_info['address']}")
        c.drawString(30, height - 90, f"Mobile: {customer_info['mobile']}")

        # Table headers
        c.drawString(30, height - 120, "S/N")
        c.drawString(80, height - 120, "Product Name")
        c.drawString(280, height - 120, "Quantity")
        c.drawString(380, height - 120, "Price")
        c.drawString(480, height - 120, "Total")

    draw_page_header()
    y_offset = height - 140
    serial_number = 1

    for i, row in invoice_df.iterrows():
        if y_offset < 100:
            c.showPage()
            draw_page_header()
            y_offset = height - 140

        c.drawString(30, y_offset, str(serial_number))
        c.drawString(80, y_offset, row['Product Name'])
        c.drawString(280, y_offset, str(row['Quantity']))
        c.drawString(380, y_offset, f"{row['DP Price']:.2f}")
        c.drawString(480, y_offset, f"{row['Total Price']:.2f}")

        y_offset -= 20
        serial_number += 1

    y_offset -= 40
    c.drawString(430, y_offset, f"Invoice Price : {total_invoice_price:.2f}")
    c.drawString(430, y_offset - 25, f"Rejection (-): {rej:.2f}")
    c.drawString(430, y_offset - 45, f"Previous Due (+): {prev_due:.2f}")
    c.drawString(430, y_offset - 65, f"Final Amount : {amt:.2f}")
    c.drawString(230, y_offset - 50, f"Payment: {payment:.2f}")
    c.drawString(230, y_offset - 80, f"New Due: {due:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# Define the login page
def login_page():
    st.title("Login Page")
    user_type = st.radio("Select Login Type:", ["Admin Login", "Staff Login"])

    if user_type == "Admin Login":
        username = st.text_input("Admin Username:")
        password = st.text_input("Admin Password:", type="password")
        if st.button("Login"):
            if username == "admin" and password == "admin123":
                st.session_state['logged_in'] = True
                st.session_state['current_user'] = "Admin"
                st.session_state['user_role'] = "admin"
                st.experimental_rerun()
            else:
                st.error("Invalid admin credentials")

    elif user_type == "Staff Login":
        username = st.text_input("Staff Username:")
        password = st.text_input("Staff Password:", type="password")
        if st.button("Login"):
            if username == "staff" and password == "staff123":
                st.session_state['logged_in'] = True
                st.session_state['current_user'] = "Staff"
                st.session_state['user_role'] = "staff"
                st.experimental_rerun()
            else:
                st.error("Invalid staff credentials")


def get_invoices_data_by_date(conn, search_date):
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT * FROM invoices WHERE invoice_date = %s
        """  # Assuming your invoices table has a 'date' column
        cursor.execute(query, (search_date,))
        invoices_data = cursor.fetchall()
        return invoices_data
    except Error as e:
        st.error(f"Error fetching invoices data: {e}")
        return []

# Admin workplace page
def admin_workplace(conn):
    st.title("Welcome, Admin!")
    st.sidebar.title("Admin Menu")
    choice = st.sidebar.radio("Select an option:", ["Register Product", "Insert Product", "Search Product", "Invoices Sheet"])

    if choice == "Register Product":
        st.subheader("Register Product")
        product_name = st.text_input("Product Name")
        dp_price = st.text_input("Distributor Price")
        mrp_price = st.text_input("MRP Price")
        group_name = st.text_input("Group Name")
        available_stock = st.number_input("Available Stock", min_value=0.0, step=0.01)  # Allow floats

        if st.button("Register"):
            if product_name and dp_price and mrp_price and group_name and available_stock:
                insert_product(conn, product_name, dp_price, mrp_price, group_name, available_stock)
            else:
                st.error("Please fill in all the required fields")

    elif choice == "Insert Product":
        st.subheader("Insert Product")
        products = get_registered_products(conn)

        if products:
            selected_product = st.selectbox("Select Product", products)

            if selected_product:
                new_quantity = st.number_input("Enter Quantity to Add", min_value=0.0, step=0.01)  # Allow floats

                if st.button("Update Stock"):
                    current_stock = get_current_stock(conn, selected_product)

                    if current_stock is not None:
                        updated_stock = current_stock + new_quantity
                        update_product_stock(conn, selected_product, updated_stock)
                    else:
                        st.error("Error: Could not retrieve current stock.")
        else:
            st.warning("No registered products found!")

    elif choice == "Search Product":
        st.subheader("Search Product")
        products = get_registered_products(conn)

        if products:
            selected_product = st.selectbox("Select Product", products)

            if selected_product:
                product_details = get_product_details_by_name(conn, selected_product)

                if product_details:
                    st.write(f"**Product ID:** {product_details['id']}")
                    st.write(f"**Product Name:** {product_details['name']}")
                    st.write(f"**Distributor Price (DP Price):** {product_details['dp_price']}")
                    st.write(f"**MRP Price:** {product_details['mrp_price']}")
                    st.write(f"**Group Name:** {product_details['group_name']}")
                    st.write(f"**Available Stock:** {product_details['available_stock']}")
                else:
                    st.error(f"Product {selected_product} not found.")
        else:
            st.warning("No registered products found!")



    elif choice == "Invoices Sheet":
        st.subheader("Invoices Sheet")
        # Add a date input for selecting the date
        selected_date = st.date_input("Select Date:")
        if st.button("Search"):
            invoices_data = get_invoices_data_by_date(conn, selected_date)
            if invoices_data:
                # Convert invoices data to DataFrame

                df = pd.DataFrame(invoices_data)

                st.write(df)  # Display the invoices data as a table

                # Calculate total payment and total due

                total_payment = df[
                    'payment'].sum() if 'payment' in df.columns else 0  # Adjust 'payment' to your actual column name

                total_due = df[
                    'new_due'].sum() if 'new_due' in df.columns else 0  # Adjust 'due' to your actual column name

                # Display total payment and total due

                st.write(f"**Total Payment:** {total_payment}")

                st.write(f"**Total Due:** {total_due}")

            else:

                st.warning(f"No data found for {selected_date}.")


# Staff workplace page
def staff_workplace(conn):
    st.title("Welcome, Staff!")
    st.sidebar.title("Staff Menu")
    choice = st.sidebar.radio("Select an option:", ["Invoice", "Search Product"])

    if choice == "Invoice":
        st.title('ISHAQ ENTERPRISE')

        customer_info = {
            'date': st.date_input('Date:', date.today()),
            'name': st.text_input('Customer Name:'),
            'address': st.text_input('Address:'),
            'mobile': st.text_input('Mobile:')
        }

        product_names = get_registered_products(conn)
        product_names = np.append(product_names, 'Manual Entry')

        selected_product_name = st.selectbox('Select Product', product_names)
        value_type = st.selectbox('Value Type', ['Piece', 'Weight'])

        if selected_product_name and selected_product_name != 'Manual Entry':
            selected_product = get_product_details_by_name(conn, selected_product_name)
            dp_price = st.number_input('Price:', value=float(selected_product['dp_price']), min_value=0.0)

            if value_type == 'Weight':
                weight = st.number_input('Weight (kg):', min_value=0.0, value=0.0, step=0.001)
                if st.button('Add to Invoice'):
                    current_stock = get_current_stock(conn, selected_product['name'])
                    if current_stock is not None:
                        if weight <= current_stock:
                            total_price = dp_price * weight
                            st.session_state.invoice.append({
                                'Product Name': selected_product['name'],
                                'Quantity': f"{weight} kg",
                                'DP Price': dp_price,
                                'Total Price': total_price,
                                'Pieces': weight  # Store weight for stock update
                            })
                        else:
                            st.error(f"Not enough stock for {selected_product['name']}. Available: {current_stock} kg, Required: {weight} kg")
            elif value_type == 'Piece':
                pieces = st.number_input('Number of Pieces:', min_value=0, value=0)
                if st.button('Add to Invoice'):
                    current_stock = get_current_stock(conn, selected_product['name'])
                    if current_stock is not None:
                        if pieces <= current_stock:
                            total_price = dp_price * pieces
                            st.session_state.invoice.append({
                                'Product Name': selected_product['name'],
                                'Quantity': f"{pieces} P",
                                'DP Price': dp_price,
                                'Total Price': total_price,
                                'Pieces': pieces  # Store pieces for stock update
                            })
                        else:
                            st.error(f"Not enough stock for {selected_product['name']}. Available: {current_stock} pieces, Required: {pieces} pieces")
        elif selected_product_name == 'Manual Entry':
            product_name = st.text_input('Product Name:')
            dp_price = st.number_input('Price:', min_value=0.0)

            if value_type == 'Weight':
                weight = st.number_input('Weight (kg):', min_value=0.0, value=0.0, step=0.001)
                if st.button('Add Manual Entry to Invoice'):
                    total_price = dp_price * weight
                    st.session_state.invoice.append({
                        'Product Name': product_name,
                        'Quantity': f"{weight} kg",
                        'DP Price': dp_price,
                        'Total Price': total_price,
                        'Pieces': weight  # Store weight for stock update
                    })
            elif value_type == 'Piece':
                pieces = st.number_input('Number of Pieces:', min_value=0, value=1)
                if st.button('Add Manual Entry to Invoice'):
                    total_price = dp_price * pieces
                    st.session_state.invoice.append({
                        'Product Name': product_name,
                        'Quantity': f"{pieces} P",
                        'DP Price': dp_price,
                        'Total Price': total_price,
                        'Pieces': pieces  # Store pieces for stock update
                    })

        # Display the current invoice
        st.subheader('Invoice')
        invoice_df = pd.DataFrame(st.session_state.invoice)

        if not invoice_df.empty:
            # Editable invoice table
            # Editable invoice table
            edited_invoice = []

            for i, row in invoice_df.iterrows():
                with st.expander(f"Edit Item {i + 1}"):
                    product_name = row['Product Name']
                    if 'kg' in row['Quantity']:  # Detect if it's weight
                        quantity = st.number_input('Quantity (kg):', value=float(row['Pieces']), min_value=0.0,
                                                   step=0.001)  # Editable for weight
                    else:  # It must be pieces
                        quantity = st.number_input('Quantity (Pieces):', value=int(row['Pieces']), min_value=0,
                                                   step=1)  # Editable for pieces

                    dp_price = st.number_input('DP Price:', value=float(row['DP Price']), min_value=0.0, step=0.01)
                    total_price = dp_price * quantity

                    # Store the correct format based on weight or pieces
                    if 'kg' in row['Quantity']:
                        edited_invoice.append({
                            'Product Name': product_name,
                            'Quantity': f"{quantity} kg",
                            'DP Price': dp_price,
                            'Pieces': quantity,
                            'Total Price': total_price
                        })
                    else:
                        edited_invoice.append({
                            'Product Name': product_name,
                            'Quantity': f"{quantity} P",
                            'DP Price': dp_price,
                            'Pieces': quantity,
                            'Total Price': total_price
                        })

            # Update the session state with edited invoice
            if st.button('Update Invoice'):
                st.session_state.invoice = edited_invoice
                st.success("Invoice updated successfully!")

            # Display updated invoice
            updated_invoice_df = pd.DataFrame(st.session_state.invoice)
            st.write(updated_invoice_df)

            total_invoice_price = updated_invoice_df['Total Price'].sum()

            # Summary inputs
            rej = st.number_input('Return Product:', min_value=0.0, value=0.0)
            prev_due = st.number_input('Previous Due:', min_value=0.0, value=0.0)
            payment = st.number_input('Payment:', min_value=0.0, value=0.0)
            due = prev_due + total_invoice_price - payment - rej
            amt = total_invoice_price - rej + prev_due

            summary_data = {
                'Total Price': total_invoice_price,
                'Return Product': rej,
                'Previous Due': prev_due,
                'Final Amount': amt,
                'Payment': payment,
                'New Due': due
            }
            summary_df = pd.DataFrame([summary_data])
            st.write(summary_df)

            if st.button('Done'):

                insert_invoice(conn, customer_info, total_price, rej, prev_due, amt, payment, due)
                # Update stock in the database
                try:
                    for item in updated_invoice_df.to_dict(orient='records'):
                        product_name = item['Product Name']
                        quantity_sold = item['Pieces']
                        current_stock = get_current_stock(conn, product_name)

                        if current_stock is not None:
                            new_stock = current_stock - quantity_sold
                            if new_stock < 0:
                                st.error(f"Not enough stock for {product_name}. Available: {current_stock}, Required: {quantity_sold}")
                                return
                            update_product_stock(conn, product_name, new_stock)

                    # Generate and download PDF after successful stock update
                    buffer = create_pdf(updated_invoice_df, customer_info, total_invoice_price, rej, prev_due, amt, payment, due)
                    file_name = f"{customer_info['name'].replace(' ', '_')}_invoice.pdf"
                    st.download_button(
                        label="Download Invoice as PDF",
                        data=buffer,
                        file_name=file_name,
                        mime="application/pdf"
                    )
                    st.session_state.invoice.clear()  # Clear the invoice after download
                except Exception as e:
                    st.error(f"Error updating stock: {e}")
        else:
            st.warning('Invoice is empty. Add products before finalizing.')


    elif choice == "Search Product":
        st.subheader("Search Product")
        products = get_registered_products(conn)

        if products:
            selected_product = st.selectbox("Select Product", products)

            if selected_product:
                product_details = get_product_details_by_name(conn, selected_product)

                if product_details:
                    st.write(f"**Product ID:** {product_details['id']}")
                    st.write(f"**Product Name:** {product_details['name']}")
                    st.write(f"**Distributor Price (DP Price):** {product_details['dp_price']}")
                    st.write(f"**MRP Price:** {product_details['mrp_price']}")
                    st.write(f"**Group Name:** {product_details['group_name']}")
                    st.write(f"**Available Stock:** {product_details['available_stock']}")
                else:
                    st.error(f"Product {selected_product} not found.")
        else:
            st.warning("No registered products found!")


# Main function to control the flow
def main():
    conn = create_connection()
    if conn:
        if st.session_state['logged_in']:
            if st.session_state['user_role'] == "admin":
                admin_workplace(conn)
            elif st.session_state['user_role'] == "staff":
                staff_workplace(conn)
        else:
            login_page()
    else:
        st.error("Failed to connect to the database")

if __name__ == "__main__":
    main()
