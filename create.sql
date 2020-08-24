CREATE TABLE users(
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    password VARCHAR NOT NULL
);

CREATE TABLE books(
    id SERIAL PRIMARY KEY,
    isbn CHAR(10) NOT NULL,
    title VARCHAR NOT NULL,
    author VARCHAR NOT NULL,
    year INTEGER NOT NULL 
);

CREATE TABLE reviews(
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users,
    book_id INTEGER REFERENCES books,
    review VARCHAR NOT NULL,
    rating INTEGER NOT NULL, 
    CHECK (rating <=5 AND rating >0)
);


