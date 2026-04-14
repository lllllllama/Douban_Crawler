CREATE TABLE IF NOT EXISTS movies (
    movie_id TEXT PRIMARY KEY,
    rank INTEGER NOT NULL,
    title_cn TEXT,
    title_foreign TEXT,
    score REAL,
    votes INTEGER,
    people_info TEXT,
    quote TEXT,
    detail_url TEXT,
    year INTEGER,
    runtime TEXT,
    genres TEXT,
    imdb_id TEXT,
    imdb_rating REAL,
    summary TEXT,
    poster_url TEXT,
    poster_path TEXT
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id TEXT NOT NULL,
    user_name TEXT,
    rating_text TEXT,
    comment_time TEXT,
    content TEXT,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id)
);
