BEGIN;

INSERT INTO bookstore.app_users (username, password_hash, email, role)
VALUES
    ('admin', 'pbkdf2_sha256$600000$5f51f58fc162103ffeb5953e02056303$b1fb4ffa2ed6574d165fc818ff8101014295429f69685d9d9d8a1e6b85185ebd', 'admin@example.com', 'admin'),
    ('manager01', 'pbkdf2_sha256$600000$a6b40690e64f3d5a2376e5ec11347384$f50e42e209b7278e52e39269555a520a7dbdc5dceb6507aa6dfa113ad4d72f67', 'manager01@example.com', 'manager'),
    ('manager02', 'pbkdf2_sha256$600000$255592cbcf432025e15a383bb6cdc874$f6db78ec20445dd7a36d03957c8ecbb5facf56e69c735bb21e30020c97f2f560', 'manager02@example.com', 'manager'),
    ('reader01', 'pbkdf2_sha256$600000$6e543ab51c160c1d19a35bb7c90682d6$0a3ffab3ede03a6dec0558a96bb2720ff6b3b2030eb70e6b1cf96002e701124f', 'reader01@example.com', 'reader'),
    ('reader02', 'pbkdf2_sha256$600000$e3447dd3a0b885a0022ed0c8ffd08579$ebcd4a7727bf5e62ea86089b681a4618a81d27997cdcc633e9c1ab54cd604fdc', 'reader02@example.com', 'reader'),
    ('reader03', 'pbkdf2_sha256$600000$fddff2966b51edb70a01f1eca2b1cbad$f17e6626a0ac60b41bf0c51f71857cee9a9ffae8c65bc51872f1ea5d3d379213', 'reader03@example.com', 'reader'),
    ('reader04', 'pbkdf2_sha256$600000$cf32119a169c8983889b44dde246c545$d9ab62cb459fe0b153c613b75716f590dc3af66a3ca9a2aba2b704873e450495', 'reader04@example.com', 'reader'),
    ('reader05', 'pbkdf2_sha256$600000$7fea6f6cad2f00301db7beec13896d3d$6896d6ec23b991af6a8df546a3dedfb2f5e4e2423e855c7f62ae62d2cd5ed88e', 'reader05@example.com', 'reader'),
    ('reader06', 'pbkdf2_sha256$600000$54847a9704d631b7fee0488e99d69dea$9cd15bb919fcf0755382dcc4b52d905a5dbd845df7cd3c2e76d73beec6edf818', 'reader06@example.com', 'reader'),
    ('reader07', 'pbkdf2_sha256$600000$ec5acc0bb4533739359f80342e978db4$839c5feb48c76d7b0fd563ea9e50e494b49ce46910934075faaf241db629fd5a', 'reader07@example.com', 'reader');

COMMIT;
