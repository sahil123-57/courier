app_name = "courier"
app_title = "Courier"
app_publisher = "Sahil"
app_description = "Parcel booking, scanning and tracking"
app_email = "sahil@example.com"
app_license = "MIT"

before_install = "courier.install.create_roles"

doc_events = {
    "Scan Event": {"after_insert": "courier.notify.on_scan_event"},
}
