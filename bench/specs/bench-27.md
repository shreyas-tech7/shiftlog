# bench-27

## sub
check: python3 -c "from f01 import sub; assert sub(5, 3) == 2"

## palin
check: python3 -c "from f02 import palin; assert palin('abba') and not palin('abc')"

## slug
check: python3 -c "from f03 import slug; assert slug('Hello Big World') == 'hello-big-world'"
