"""
Bu modül, temel matematiksel işlemler için yardımcı fonksiyonlar sağlar.
Özellikle, Fibonacci dizisi oluşturma işlevini içerir.
"""

from typing import List, Union

def generate_fibonacci_sequence(limit: int) -> List[int]:
    """
    Belirtilen sınıra kadar bir Fibonacci dizisi oluşturur.

    Fibonacci dizisi, her sayının kendinden önceki iki sayının toplamı olduğu
    bir sayı dizisidir, genellikle 0 ve 1 ile başlar.

    Args:
        limit: Dizide oluşturulacak maksimum eleman sayısı.
               Negatif olmayan bir tam sayı olmalıdır.

    Returns:
        Fibonacci dizisini temsil eden tam sayıların bir listesi.
        Eğer limit 0 veya negatif ise boş bir liste döndürür.

    Raises:
        ValueError: Eğer limit bir tam sayı değilse.
    """
    if not isinstance(limit, int):
        raise ValueError("Limit bir tam sayı olmalıdır.")

    if limit <= 0:
        return []
    elif limit == 1:
        return [0]
    elif limit == 2:
        return [0, 1]

    sequence: List[int] = [0, 1]
    # Dizinin uzunluğu limite ulaşana kadar devam et
    while len(sequence) < limit:
        next_fib = sequence[-1] + sequence[-2]
        sequence.append(next_fib)
    return sequence

if __name__ == '__main__':
    print("--- Fibonacci Dizisi Oluşturucu ---")
    print("Bu blok, 'generate_fibonacci_sequence' fonksiyonunun kullanımını ve testlerini gösterir.")

    # Test Durumu 1: Geçerli pozitif limit
    limit_1 = 10
    print(f"\nTest 1: {limit_1} elemana kadar Fibonacci dizisi oluşturuluyor.")
    try:
        fib_seq_1 = generate_fibonacci_sequence(limit_1)
        print(f"Sonuç: {fib_seq_1}")
        expected_1 = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        assert fib_seq_1 == expected_1, f"Test 1 Başarısız: Beklenen {expected_1}, Alınan {fib_seq_1}"
        print("Test 1 Başarılı.")
    except Exception as e:
        print(f"Test 1 Hata: {e}")

    # Test Durumu 2: Limit 1
    limit_2 = 1
    print(f"\nTest 2: {limit_2} elemana kadar Fibonacci dizisi oluşturuluyor.")
    try:
        fib_seq_2 = generate_fibonacci_sequence(limit_2)
        print(f"Sonuç: {fib_seq_2}")
        expected_2 = [0]
        assert fib_seq_2 == expected_2, f"Test 2 Başarısız: Beklenen {expected_2}, Alınan {fib_seq_2}"
        print("Test 2 Başarılı.")
    except Exception as e:
        print(f"Test 2 Hata: {e}")

    # Test Durumu 3: Limit 2
    limit_3 = 2
    print(f"\nTest 3: {limit_3} elemana kadar Fibonacci dizisi oluşturuluyor.")
    try:
        fib_seq_3 = generate_fibonacci_sequence(limit_3)
        print(f"Sonuç: {fib_seq_3}")
        expected_3 = [0, 1]
        assert fib_seq_3 == expected_3, f"Test 3 Başarısız: Beklenen {expected_3}, Alınan {fib_seq_3}"
        print("Test 3 Başarılı.")
    except Exception as e:
        print(f"Test 3 Hata: {e}")

    # Test Durumu 4: Sıfır limit
    limit_4 = 0
    print(f"\nTest 4: {limit_4} elemana kadar Fibonacci dizisi oluşturuluyor.")
    try:
        fib_seq_4 = generate_fibonacci_sequence(limit_4)
        print(f"Sonuç: {fib_seq_4}")
        expected_4 = []
        assert fib_seq_4 == expected_4, f"Test 4 Başarısız: Beklenen {expected_4}, Alınan {fib_seq_4}"
        print("Test 4 Başarılı.")
    except Exception as e:
        print(f"Test 4 Hata: {e}")

    # Test Durumu 5: Negatif limit (boş liste döndürmeli)
    limit_5 = -5
    print(f"\nTest 5: Negatif limit ({limit_5}) ile Fibonacci dizisi oluşturuluyor.")
    try:
        fib_seq_5 = generate_fibonacci_sequence(limit_5)
        print(f"Sonuç: {fib_seq_5}")
        expected_5 = []
        assert fib_seq_5 == expected_5, f"Test 5 Başarısız: Beklenen {expected_5}, Alınan {fib_seq_5}"
        print("Test 5 Başarılı.")
    except Exception as e:
        print(f"Test 5 Hata: {e}")

    # Test Durumu 6: Geçersiz giriş tipi (ValueError yükseltmeli)
    limit_6: Union[str, int] = "abc"
    print(f"\nTest 6: Geçersiz giriş tipi ('{limit_6}') ile test ediliyor.")
    try:
        generate_fibonacci_sequence(limit_6)
        print("Test 6 Başarısız: ValueError yükseltilmedi.")
    except ValueError as e:
        print(f"Beklenen hata yakalandı: {e}")
        print("Test 6 Başarılı.")
    except Exception as e:
        print(f"Test 6 Hata: Beklenmeyen hata: {e}")

    print("\n--- Tüm testler tamamlandı. ---")