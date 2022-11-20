import math

def elementwise_mul(arg1: list, arg2: list):
    result = []

    if len(arg1) != len(arg2):
        return result

    for i in range(0, len(arg1), 1):
        result.append(arg1[i] * arg2[i])

    return result

class regulator:
    def __call__(this, x1_val: float, x2_val: float, x3_val: float):
        vector_len = math.sqrt(x2_val**2 + x1_val**2)
        if vector_len > 100.0:
            vector_len = 100.0

        if abs(x3_val) < 40:
            u1_coefs = [-40, -100, -100, 0, 0, 100, 40, 100, 100]
            u2_coefs = [-100, -100, -40, 100, 0, 0, 100, 100, 40]
            betas = []

            betas.append(x1_val <= -15 and x2_val <= -15)
            betas.append(x1_val <= -15 and x2_val > -15 and x2_val < 15)
            betas.append(x1_val <= -15 and x2_val >= 15)

            betas.append(x1_val > -15 and x1_val < 15 and x2_val <= -15)
            betas.append(x1_val > -15 and x1_val < 15 and x2_val > -15 and x2_val < 15)
            betas.append(x1_val > -15 and x1_val < 15 and x2_val >= 15)

            betas.append(x1_val > 15 and x2_val <= -15)
            betas.append(x1_val > 15 and x2_val > -15 and x2_val < 15)
            betas.append(x1_val > 15 and x2_val >= 15)

            nom1 = sum(elementwise_mul(u1_coefs, betas))
            nom2 = sum(elementwise_mul(u2_coefs, betas))
            den = sum(betas)

            vector_len_coef = vector_len / 100.0

            u1_val = vector_len_coef * nom1 / den
            u2_val = vector_len_coef * nom2 / den
        else:
            sign1 = 1.0
            sign2 = 1.0

            u1_val = u2_val = abs(x3_val)

            if x3_val < 0:
                sign1 = -1.0
            else:
                sign2 = -1.0

            u1_val = sign1 * u1_val
            u2_val = sign2 * u2_val

        return (u1_val, u2_val)

def translate_hat(hat_readings: tuple):
    """
    Function translates hat coords into one digit containing flags\n
    Return value: integer containing flags |Right(MSB) | Left | Up | Down(LSB)|
    """

    result = 0

    if hat_readings[0] == 1:
        result += 8
    elif hat_readings[0] == -1:
        result += 4
    if hat_readings[1] == 1:
        result += 2
    elif hat_readings[1] == -1:
        result += 1

    return result