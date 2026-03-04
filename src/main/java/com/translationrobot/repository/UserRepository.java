package com.translationrobot.repository;

import com.translationrobot.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * Spring Data JPA repository for the {@link User} entity.
 * Provides standard CRUD operations and null-safe lookup methods using Java 8 Optional.
 */
@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    /**
     * Finds a user by their email address, ignoring case, and wraps the result in an {@link Optional}.
     *
     * @param email The email address to search for.
     * @return An {@link Optional} containing the found {@link User}, or an empty Optional if not found.
     */
    Optional<User> findByEmailIgnoreCase(String email);

    /**
     * Finds a user by their username and wraps the result in an {@link Optional}.
     *
     * @param username The username to search for.
     * @return An {@link Optional} containing the found {@link User}, or an empty Optional if not found.
     */
    Optional<User> findByUsername(String username);
}
