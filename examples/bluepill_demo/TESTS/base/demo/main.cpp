#include "greentea-client/test_env.h"
#include "mbed.h"
#include "unity.h"
#include "utest.h"

using namespace utest::v1;

//--------------------------------
// test setup functions
//--------------------------------

static utest::v1::status_t app_test_setup_handler(const size_t number_of_cases)
{
    // common setup code ...
    return greentea_test_setup_handler(number_of_cases);
}

static utest::v1::status_t app_case_setup_handler(const Case *const source, const size_t index_of_case)
{
    // test setup code ...
    return greentea_case_setup_handler(source, index_of_case);
}

static utest::v1::status_t app_case_teardown_handler(const Case *const source, const size_t passed, const size_t failed, const failure_t failure)
{
    // test tear down code ...
    return greentea_case_teardown_handler(source, passed, failed, failure);
}

static void app_test_teardown_handler(const size_t passed, const size_t failed, const failure_t failure)
{
    // common tear down code
    return greentea_test_teardown_handler(passed, failed, failure);
}

//--------------------------------
// test functions
//--------------------------------

static void test_success_1()
{
    TEST_ASSERT_EQUAL(0, 0);
}

static void test_success_2()
{
    TEST_ASSERT_EQUAL(1, 1);
}

// test cases description
#define SimpleCase(test_fun) Case(#test_fun, app_case_setup_handler, test_fun, app_case_teardown_handler, greentea_case_failure_continue_handler)
static Case cases[] = {
    SimpleCase(test_success_1),
    SimpleCase(test_success_2)

};
static Specification specification(app_test_setup_handler, cases, app_test_teardown_handler);

// Entry point into the tests
int main()
{
    // host handshake
    // note: should be invoked here or in the test_setup_handler
    GREENTEA_SETUP(40, "default_auto");
    // run tests
    return !Harness::run(specification);
}
