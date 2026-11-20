# bench-16

## palin
check: python3 -c "from f01 import palin; assert palin('abba') and not palin('abc')"

## vowels
check: python3 -c "from f02 import vowels; assert vowels('Banana') == 3"

## slug
check: python3 -c "from f03 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## reverse
check: python3 -c "from f04 import reverse; assert reverse('abc') == 'cba'"
