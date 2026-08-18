CREATE TABLE alias (
    location_code TEXT,
    alias TEXT,
    CONSTRAINT location
    FOREIGN KEY (location_code)
    REFERENCES location_code(location_code)
)